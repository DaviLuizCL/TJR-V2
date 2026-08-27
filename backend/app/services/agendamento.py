from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.agendamento import Agendamento
from app.models.arena import Arena
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.modalidade import Modalidade, TipoDisputa
from app.models.rodada import ModoHorario, Rodada
from app.services.audit import registrar_audit_log
from app.services.modalidade import obter_modalidade

# Par fixo (TJR 2026): equipe nas duas modalidades nao pode ter bateria no
# mesmo instante, porque o robo pode ser o mesmo fisico. Resolvido aqui, nao
# generalizado pra uma tabela de config - unico par que existe hoje.
_MODALIDADES_AGENDA_CONFLITANTE: dict[str, str] = {
    "Resgate no Plano": "Resgate de Alto Risco",
    "Resgate de Alto Risco": "Resgate no Plano",
}


async def _horarios_ja_ocupados_no_par(
    db: AsyncSession, modalidade: Modalidade, equipe_ids: list[UUID]
) -> dict[UUID, set[datetime]]:
    nome_par = _MODALIDADES_AGENDA_CONFLITANTE.get(modalidade.nome)
    if nome_par is None or not equipe_ids:
        return {}

    resultado = await db.execute(
        select(Agendamento.equipe_id, Agendamento.horario_inicio)
        .join(Rodada, Agendamento.rodada_id == Rodada.id)
        .join(Modalidade, Rodada.modalidade_id == Modalidade.id)
        .where(
            Modalidade.evento_id == modalidade.evento_id,
            Modalidade.nome == nome_par,
            Agendamento.equipe_id.in_(equipe_ids),
        )
    )
    ocupados: dict[UUID, set[datetime]] = defaultdict(set)
    for equipe_id, horario in resultado.all():
        ocupados[equipe_id].add(horario)
    return ocupados


def _serializar_agendamento(agendamento: Agendamento) -> dict:
    return {
        "equipe_id": str(agendamento.equipe_id),
        "arena_id": str(agendamento.arena_id),
        "ordem_na_arena": agendamento.ordem_na_arena,
        "horario_inicio": agendamento.horario_inicio.isoformat(),
    }


async def _carregar_rodadas_ordenadas(
    db: AsyncSession, modalidade_id: UUID, rodada_ids: list[UUID]
) -> list[Rodada]:
    resultado = await db.execute(select(Rodada).where(Rodada.id.in_(rodada_ids)))
    rodadas_por_id = {r.id: r for r in resultado.scalars().all()}

    faltando = set(rodada_ids) - set(rodadas_por_id)
    if faltando:
        raise AppError(
            codigo="RODADA_NAO_ENCONTRADA", mensagem="Rodada nao encontrada.", status_code=404
        )

    for rodada in rodadas_por_id.values():
        if rodada.modalidade_id != modalidade_id:
            raise AppError(
                codigo="RODADA_NAO_PERTENCE_A_MODALIDADE",
                mensagem="A rodada informada nao pertence a esta modalidade.",
                status_code=422,
            )

    return sorted(rodadas_por_id.values(), key=lambda r: r.numero)


async def _carregar_arenas_ativas(db: AsyncSession, modalidade_id: UUID) -> list[Arena]:
    resultado = await db.execute(
        select(Arena).where(Arena.modalidade_id == modalidade_id, Arena.ativo.is_(True))
    )
    arenas = list(resultado.scalars().all())
    if not arenas:
        raise AppError(
            codigo="ARENAS_NAO_CADASTRADAS",
            mensagem="Nenhuma arena ativa cadastrada para esta modalidade.",
            status_code=422,
        )
    return arenas


async def _carregar_equipes_inscritas(
    db: AsyncSession, modalidade_id: UUID
) -> list[tuple[UUID, int]]:
    resultado = await db.execute(
        select(Inscricao.equipe_id, Equipe.nivel)
        .join(Equipe, Inscricao.equipe_id == Equipe.id)
        .where(Inscricao.modalidade_id == modalidade_id)
        .order_by(Inscricao.equipe_id)
    )
    return list(resultado.all())


def _arenas_elegiveis_por_equipe(
    equipes: list[tuple[UUID, int]], arenas: list[Arena]
) -> dict[UUID, set[UUID]]:
    elegiveis: dict[UUID, set[UUID]] = {}
    for equipe_id, nivel in equipes:
        elegiveis[equipe_id] = {
            arena.id
            for arena in arenas
            if arena.niveis_aplicaveis is None or nivel in arena.niveis_aplicaveis
        }
        if not elegiveis[equipe_id]:
            raise AppError(
                codigo="ARENA_ELEGIVEL_INEXISTENTE",
                mensagem="Nao ha arena elegivel para uma das equipes inscritas.",
                status_code=422,
                detalhes={"equipe_id": str(equipe_id), "nivel": nivel},
            )
    return elegiveis


async def _carregar_historico_de_arenas_usadas(
    db: AsyncSession, modalidade_id: UUID
) -> dict[UUID, set[UUID]]:
    resultado = await db.execute(
        select(Agendamento.equipe_id, Agendamento.arena_id)
        .join(Rodada, Agendamento.rodada_id == Rodada.id)
        .where(Rodada.modalidade_id == modalidade_id)
    )
    usados: dict[UUID, set[UUID]] = defaultdict(set)
    for equipe_id, arena_id in resultado.all():
        usados[equipe_id].add(arena_id)
    return usados


async def gerar_agendamentos(
    db: AsyncSession,
    modalidade_id: UUID,
    rodada_ids: list[UUID],
    horario_inicio: datetime,
    *,
    regenerar: bool = False,
    usuario_id: UUID,
) -> list[Agendamento]:
    modalidade: Modalidade = await obter_modalidade(db, modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.INDIVIDUAL:
        raise AppError(
            codigo="MODALIDADE_NAO_E_INDIVIDUAL",
            mensagem="Agendamento de horario so e suportado em modalidades INDIVIDUAL.",
            status_code=422,
        )
    if modalidade.duracao_maxima_rodada_seg is None:
        raise AppError(
            codigo="DURACAO_RODADA_NAO_CONFIGURADA",
            mensagem="Configure duracao_maxima_rodada_seg na modalidade antes de gerar horario.",
            status_code=422,
        )

    rodadas_ordenadas = await _carregar_rodadas_ordenadas(db, modalidade_id, rodada_ids)
    arenas = await _carregar_arenas_ativas(db, modalidade_id)
    equipes = await _carregar_equipes_inscritas(db, modalidade_id)
    elegiveis = _arenas_elegiveis_por_equipe(equipes, arenas)

    existentes = await db.execute(select(Agendamento).where(Agendamento.rodada_id.in_(rodada_ids)))
    existentes = list(existentes.scalars().all())
    antes_por_rodada: dict[UUID, list[dict]] = defaultdict(list)
    if existentes:
        if not regenerar:
            numeros = sorted(
                {r.numero for r in rodadas_ordenadas if r.id in {a.rodada_id for a in existentes}}
            )
            raise AppError(
                codigo="AGENDAMENTO_JA_EXISTE",
                mensagem="Ja existe horario gerado para uma ou mais rodadas selecionadas.",
                status_code=409,
                detalhes={"rodada_numeros": numeros},
            )
        for agendamento in existentes:
            antes_por_rodada[agendamento.rodada_id].append(_serializar_agendamento(agendamento))
        await db.execute(delete(Agendamento).where(Agendamento.rodada_id.in_(rodada_ids)))
        await db.flush()

    usados_por_equipe = await _carregar_historico_de_arenas_usadas(db, modalidade_id)
    horarios_ocupados_no_par = await _horarios_ja_ocupados_no_par(
        db, modalidade, [equipe_id for equipe_id, _nivel in equipes]
    )

    duracao = modalidade.duracao_maxima_rodada_seg
    pausa = modalidade.pausa_entre_rodadas_seg or 0

    todos_os_novos: list[Agendamento] = []
    rodada_horario_inicio = horario_inicio

    for rodada in rodadas_ordenadas:
        fila_por_arena: dict[UUID, int] = {arena.id: 0 for arena in arenas}
        novos_da_rodada: list[Agendamento] = []

        for equipe_id, _nivel in sorted(equipes, key=lambda item: str(item[0])):
            elegiveis_eq = elegiveis[equipe_id]
            nao_usadas = elegiveis_eq - usados_por_equipe[equipe_id]
            preferidas = nao_usadas or elegiveis_eq

            arena_escolhida = min(preferidas, key=lambda a_id: (fila_por_arena[a_id], str(a_id)))

            ordem = fila_por_arena[arena_escolhida]
            horario_equipe = rodada_horario_inicio + timedelta(seconds=ordem * duracao)

            # Se esse instante ja esta reservado pra essa equipe na
            # modalidade pareada (mesmo robo fisico possivel), pula pra
            # proxima posicao da mesma arena ate achar um horario livre -
            # nunca deixa a equipe sem agendamento, so desvia da colisao.
            # Bound de seguranca (nao pode ficar preso num loop infinito
            # numa distribuicao patologica de horarios ocupados).
            ocupados = horarios_ocupados_no_par.get(equipe_id, set())
            tentativas = 0
            while horario_equipe in ocupados and tentativas <= len(equipes):
                fila_por_arena[arena_escolhida] += 1
                ordem = fila_por_arena[arena_escolhida]
                horario_equipe = rodada_horario_inicio + timedelta(seconds=ordem * duracao)
                tentativas += 1

            agendamento = Agendamento(
                rodada_id=rodada.id,
                equipe_id=equipe_id,
                arena_id=arena_escolhida,
                ordem_na_arena=ordem,
                horario_inicio=horario_equipe,
            )
            db.add(agendamento)
            novos_da_rodada.append(agendamento)

            fila_por_arena[arena_escolhida] += 1
            usados_por_equipe[equipe_id].add(arena_escolhida)

        rodada.horario_inicio = rodada_horario_inicio
        rodada.modo_horario = ModoHorario.AUTOMATICO
        await db.flush()

        await registrar_audit_log(
            db,
            usuario_id=usuario_id,
            entidade="rodada",
            entidade_id=rodada.id,
            acao="REGERAR_AGENDAMENTO" if regenerar else "GERAR_AGENDAMENTO",
            antes={"agendamentos": antes_por_rodada.get(rodada.id, [])} if regenerar else None,
            depois={"agendamentos": [_serializar_agendamento(a) for a in novos_da_rodada]},
        )

        todos_os_novos.extend(novos_da_rodada)

        maior_fila = max(fila_por_arena.values())
        rodada_horario_inicio = rodada_horario_inicio + timedelta(
            seconds=maior_fila * duracao + pausa
        )

    return todos_os_novos


async def estimar_horarios(db: AsyncSession, modalidade_id: UUID) -> dict[UUID, datetime]:
    """Reprojeta o horario previsto das baterias que ainda nao foram
    pontuadas, usando a confirmacao real dos lancamentos como marco: o
    intervalo observado entre confirmacoes consecutivas na mesma arena vira
    o novo ritmo daquela arena (substituindo duracao_maxima_rodada_seg
    enquanto nao houver pelo menos duas confirmacoes reais pra calcular um
    intervalo), e o atraso/adiantamento acumulado cascateia pro inicio
    estimado das proximas rodadas (mesma formula de pausa_entre_rodadas_seg
    usada em gerar_agendamentos). Baterias ja confirmadas nao entram no
    resultado -- ja aconteceram, nao ha "previsto" a mostrar.
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    duracao_padrao = modalidade.duracao_maxima_rodada_seg or 0
    pausa = modalidade.pausa_entre_rodadas_seg or 0

    resultado_rodadas = await db.execute(
        select(Rodada)
        .join(Agendamento, Agendamento.rodada_id == Rodada.id)
        .where(Rodada.modalidade_id == modalidade_id)
        .distinct()
    )
    rodadas = sorted(resultado_rodadas.scalars().all(), key=lambda r: r.numero)
    if not rodadas:
        return {}

    rodada_ids = [r.id for r in rodadas]

    resultado_agendamentos = await db.execute(
        select(Agendamento)
        .where(Agendamento.rodada_id.in_(rodada_ids))
        .order_by(Agendamento.ordem_na_arena)
    )
    agendamentos_por_rodada_arena: dict[tuple[UUID, UUID], list[Agendamento]] = defaultdict(list)
    for agendamento in resultado_agendamentos.scalars().all():
        agendamentos_por_rodada_arena[(agendamento.rodada_id, agendamento.arena_id)].append(
            agendamento
        )

    resultado_confirmados = await db.execute(
        select(
            Lancamento.equipe_id,
            Lancamento.rodada_id,
            func.max(Lancamento.atualizado_em),
        )
        .where(
            Lancamento.rodada_id.in_(rodada_ids),
            Lancamento.status == LancamentoStatus.CONFIRMADO,
        )
        .group_by(Lancamento.equipe_id, Lancamento.rodada_id)
    )
    conclusao_real: dict[tuple[UUID, UUID], datetime] = {
        (equipe_id, rodada_id): momento for equipe_id, rodada_id, momento in resultado_confirmados
    }

    arena_ids = {arena_id for (_, arena_id) in agendamentos_por_rodada_arena}
    pace_por_arena: dict[UUID, float] = dict.fromkeys(arena_ids, duracao_padrao)

    previsto: dict[UUID, datetime] = {}
    inicio_rodada = rodadas[0].horario_inicio

    for rodada in rodadas:
        fim_por_arena: list[datetime] = []

        for arena_id in arena_ids:
            fila = agendamentos_por_rodada_arena.get((rodada.id, arena_id))
            if not fila:
                continue

            hora_corrente = inicio_rodada
            primeira = True
            for agendamento in fila:
                anterior = hora_corrente
                real = conclusao_real.get((agendamento.equipe_id, rodada.id))
                if real is not None:
                    if not primeira:
                        gap = (real - anterior).total_seconds()
                        if gap > 0:
                            pace_por_arena[arena_id] = gap
                    hora_corrente = real
                else:
                    if not primeira:
                        hora_corrente = anterior + timedelta(seconds=pace_por_arena[arena_id])
                    previsto[agendamento.id] = hora_corrente
                primeira = False

            fim_por_arena.append(hora_corrente)

        if fim_por_arena:
            inicio_rodada = max(fim_por_arena) + timedelta(seconds=pausa)
        else:
            inicio_rodada = inicio_rodada + timedelta(seconds=pausa)

    return previsto


async def listar_agendamentos(
    db: AsyncSession,
    *,
    modalidade_id: UUID | None,
    rodada_id: UUID | None,
    arena_id: UUID | None,
    equipe_id: UUID | None,
    page: int,
    size: int,
) -> tuple[list[Agendamento], int]:
    stmt = select(Agendamento)
    count_stmt = select(func.count()).select_from(Agendamento)
    if modalidade_id is not None:
        stmt = stmt.join(Rodada, Agendamento.rodada_id == Rodada.id).where(
            Rodada.modalidade_id == modalidade_id
        )
        count_stmt = count_stmt.join(Rodada, Agendamento.rodada_id == Rodada.id).where(
            Rodada.modalidade_id == modalidade_id
        )
    if rodada_id is not None:
        stmt = stmt.where(Agendamento.rodada_id == rodada_id)
        count_stmt = count_stmt.where(Agendamento.rodada_id == rodada_id)
    if arena_id is not None:
        stmt = stmt.where(Agendamento.arena_id == arena_id)
        count_stmt = count_stmt.where(Agendamento.arena_id == arena_id)
    if equipe_id is not None:
        stmt = stmt.where(Agendamento.equipe_id == equipe_id)
        count_stmt = count_stmt.where(Agendamento.equipe_id == equipe_id)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(
        stmt.order_by(Agendamento.horario_inicio).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0
