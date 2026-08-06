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
from app.models.modalidade import Modalidade, TipoDisputa
from app.models.rodada import ModoHorario, Rodada
from app.services.audit import registrar_audit_log
from app.services.modalidade import obter_modalidade


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
