from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipe import Equipe
from app.models.ficha import Ficha, FichaStatus
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import Consolidacao, FormatoChaveamento, Modalidade, TipoDisputa
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import Rodada
from app.services.chaveamento import LIMITE_EQUIPES_TODOS_CONTRA_TODOS
from app.services.modalidade import obter_modalidade


async def calcular_classificacao(db: AsyncSession, modalidade_id: UUID) -> list[dict]:
    """Calcula a classificacao das equipes inscritas numa modalidade.

    Individual: soma/melhor rodada dos totais lancados (comportamento
    original, com desempates configuraveis).

    Confronto: cada nivel pode estar num formato diferente (ver
    `_formato_por_nivel`/`gerar_chaveamento_confronto`) - todos-contra-todos
    usa pontos de liga (vitoria/empate/derrota, `modalidade.pontos_vitoria`/
    `pontos_empate`); mata-mata nao tem nota, so vitorias/derrotas (ordenado
    por vitorias) e aponta quem eliminou a equipe.
    """
    modalidade = await obter_modalidade(db, modalidade_id)

    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        return await _classificacao_confronto(db, modalidade)

    return await _classificacao_individual(db, modalidade)


async def _formato_por_nivel(
    db: AsyncSession, modalidade: Modalidade
) -> dict[int, FormatoChaveamento]:
    """Formato de cada nivel pra fins de classificacao: o que a(s) partida(s)
    ja geradas daquele nivel decidiram (fonte da verdade, gravada em
    Partida.formato_chaveamento no momento da criacao - ver
    gerar_chaveamento_confronto), ou uma previa pela mesma regra de
    contagem quando o nivel ainda nao tem chaveamento gerado.
    """
    resultado = await db.execute(
        select(Partida.nivel, Partida.formato_chaveamento)
        .join(Rodada, Partida.rodada_id == Rodada.id)
        .where(Rodada.modalidade_id == modalidade.id, Partida.nivel.is_not(None))
        .distinct()
    )
    ja_decidido = dict(resultado.all())

    contagem_por_nivel: dict[int, int] = defaultdict(int)
    for nivel in (await _equipes_por_nivel(db, modalidade.id)).values():
        contagem_por_nivel[nivel] += 1

    formatos: dict[int, FormatoChaveamento] = {}
    for nivel, qtd in contagem_por_nivel.items():
        if nivel in ja_decidido:
            formatos[nivel] = ja_decidido[nivel]
        elif modalidade.formato_chaveamento is not None:
            formatos[nivel] = modalidade.formato_chaveamento
        else:
            formatos[nivel] = (
                FormatoChaveamento.TODOS_CONTRA_TODOS
                if qtd <= LIMITE_EQUIPES_TODOS_CONTRA_TODOS
                else FormatoChaveamento.MATA_MATA
            )
    return formatos


async def _classificacao_confronto(db: AsyncSession, modalidade: Modalidade) -> list[dict]:
    formato_por_nivel = await _formato_por_nivel(db, modalidade)
    niveis_bracket = {
        nivel
        for nivel, formato in formato_por_nivel.items()
        if formato == FormatoChaveamento.MATA_MATA
    }
    niveis_liga = {
        nivel
        for nivel, formato in formato_por_nivel.items()
        if formato == FormatoChaveamento.TODOS_CONTRA_TODOS
    }

    resultados: list[dict] = []
    if niveis_bracket:
        resultados.extend(await _classificacao_bracket(db, modalidade, niveis_bracket))
    if niveis_liga:
        resultados.extend(await _classificacao_todos_contra_todos(db, modalidade, niveis_liga))
    return resultados


async def _buscar_partidas_decididas(db: AsyncSession, modalidade_id: UUID) -> list[Partida]:
    resultado = await db.execute(
        select(Partida)
        .join(Rodada, Partida.rodada_id == Rodada.id)
        .where(
            Rodada.modalidade_id == modalidade_id,
            Partida.status.in_((PartidaStatus.ENCERRADA, PartidaStatus.EMPATADA)),
        )
    )
    return list(resultado.scalars().all())


async def _equipes_inscritas(db: AsyncSession, modalidade_id: UUID) -> list[UUID]:
    return list(
        (
            await db.scalars(
                select(Inscricao.equipe_id).where(Inscricao.modalidade_id == modalidade_id)
            )
        ).all()
    )


async def _equipes_por_nivel(db: AsyncSession, modalidade_id: UUID) -> dict[UUID, int]:
    resultado = await db.execute(
        select(Equipe.id, Equipe.nivel)
        .join(Inscricao, Inscricao.equipe_id == Equipe.id)
        .where(Inscricao.modalidade_id == modalidade_id)
    )
    return dict(resultado.all())


def _atribuir_posicoes_por_nivel(
    resultados: list[dict],
    niveis_por_equipe: dict[UUID, int],
    chave_ordenacao,
) -> list[dict]:
    """Numera `posicao` 1..N dentro de cada nivel, nunca cruzando niveis
    diferentes na mesma contagem — equipes de niveis diferentes nunca se
    enfrentam (regra inviolavel 9), e tambem nao devem competir por posicao
    de classificacao entre si.
    """
    por_nivel: dict[int | None, list[dict]] = defaultdict(list)
    for resultado in resultados:
        nivel = niveis_por_equipe.get(resultado["equipe_id"])
        por_nivel[nivel].append(resultado)

    finais: list[dict] = []
    for nivel in sorted(por_nivel, key=lambda n: (n is None, n)):
        grupo = sorted(por_nivel[nivel], key=chave_ordenacao)
        for posicao, resultado in enumerate(grupo, start=1):
            resultado["posicao"] = posicao
        finais.extend(grupo)
    return finais


def _ordenar_com_desempate_confronto_direto(
    resultados: list[dict], partidas: list[Partida]
) -> list[dict]:
    """Agrupa equipes empatadas em nota_final e desempata por confronto
    direto (quem venceu o jogo entre as empatadas fica na frente); se elas
    tambem empataram entre si ou nunca jogaram entre si, cai pra mais
    vitorias no total. Resto que ainda empatar fica em ordem estavel
    (arbitraria).
    """
    por_nota: dict[Decimal, list[dict]] = defaultdict(list)
    for resultado in resultados:
        por_nota[resultado["nota_final"]].append(resultado)

    ordenados: list[dict] = []
    for nota in sorted(por_nota, reverse=True):
        grupo = por_nota[nota]
        if len(grupo) == 1:
            ordenados.extend(grupo)
            continue

        ids_grupo = {r["equipe_id"] for r in grupo}
        vitorias_diretas = {equipe_id: 0 for equipe_id in ids_grupo}
        for partida in partidas:
            if partida.status != PartidaStatus.ENCERRADA:
                continue
            if partida.equipe_a_id in ids_grupo and partida.equipe_b_id in ids_grupo:
                if partida.vencedor_id in ids_grupo:
                    vitorias_diretas[partida.vencedor_id] += 1

        ordenados.extend(
            sorted(grupo, key=lambda r: (-vitorias_diretas[r["equipe_id"]], -r["vitorias"]))
        )
    return ordenados


async def _classificacao_todos_contra_todos(
    db: AsyncSession, modalidade: Modalidade, niveis: set[int]
) -> list[dict]:
    niveis_por_equipe = await _equipes_por_nivel(db, modalidade.id)
    # Filtra por equipe (nao por partida.nivel): fixture antiga pode deixar
    # Partida.nivel em branco mesmo a equipe pertencendo a um nivel de
    # verdade - a associacao equipe->nivel via Equipe.nivel e que manda, o
    # loop de stats abaixo ja ignora partida cujas equipes nao estao aqui.
    partidas = await _buscar_partidas_decididas(db, modalidade.id)
    equipe_ids = [
        eid
        for eid in await _equipes_inscritas(db, modalidade.id)
        if niveis_por_equipe.get(eid) in niveis
    ]

    stats = {eid: {"vitorias": 0, "empates": 0, "derrotas": 0} for eid in equipe_ids}
    for partida in partidas:
        lados = [e for e in (partida.equipe_a_id, partida.equipe_b_id) if e is not None]
        for equipe_id in lados:
            if equipe_id not in stats:
                continue
            if partida.status == PartidaStatus.EMPATADA:
                stats[equipe_id]["empates"] += 1
            elif equipe_id == partida.vencedor_id:
                stats[equipe_id]["vitorias"] += 1
            else:
                stats[equipe_id]["derrotas"] += 1

    pontos_vitoria = Decimal(str(modalidade.pontos_vitoria))
    pontos_empate = Decimal(str(modalidade.pontos_empate))

    resultados = []
    for equipe_id in equipe_ids:
        s = stats[equipe_id]
        nota_final = s["vitorias"] * pontos_vitoria + s["empates"] * pontos_empate
        resultados.append(
            {
                "equipe_id": equipe_id,
                "nota_final": nota_final,
                "vitorias": s["vitorias"],
                "empates": s["empates"],
                "derrotas": s["derrotas"],
                "eliminado_por_equipe_id": None,
                "formato_chaveamento": FormatoChaveamento.TODOS_CONTRA_TODOS,
            }
        )

    resultados = _ordenar_com_desempate_confronto_direto(resultados, partidas)
    return _atribuir_posicoes_por_nivel(resultados, niveis_por_equipe, lambda r: -r["nota_final"])


async def _classificacao_bracket(
    db: AsyncSession, modalidade: Modalidade, niveis: set[int]
) -> list[dict]:
    niveis_por_equipe = await _equipes_por_nivel(db, modalidade.id)
    partidas = await _buscar_partidas_decididas(db, modalidade.id)
    equipe_ids = [
        eid
        for eid in await _equipes_inscritas(db, modalidade.id)
        if niveis_por_equipe.get(eid) in niveis
    ]

    stats = {eid: {"vitorias": 0, "derrotas": 0, "eliminado_por": None} for eid in equipe_ids}
    for partida in partidas:
        if partida.status != PartidaStatus.ENCERRADA:
            continue
        lados = [e for e in (partida.equipe_a_id, partida.equipe_b_id) if e is not None]
        for equipe_id in lados:
            if equipe_id not in stats:
                continue
            if equipe_id == partida.vencedor_id:
                stats[equipe_id]["vitorias"] += 1
            else:
                stats[equipe_id]["derrotas"] += 1
                stats[equipe_id]["eliminado_por"] = partida.vencedor_id

    resultados = []
    for equipe_id in equipe_ids:
        s = stats[equipe_id]
        resultados.append(
            {
                "equipe_id": equipe_id,
                "nota_final": Decimal("0"),
                "vitorias": s["vitorias"],
                "empates": 0,
                "derrotas": s["derrotas"],
                "eliminado_por_equipe_id": s["eliminado_por"],
                "formato_chaveamento": FormatoChaveamento.MATA_MATA,
            }
        )

    return _atribuir_posicoes_por_nivel(
        resultados, niveis_por_equipe, lambda r: (-r["vitorias"], r["derrotas"])
    )


async def _classificacao_individual(db: AsyncSession, modalidade: Modalidade) -> list[dict]:
    """Comportamento original (fase 1-3): soma/melhor rodada dos totais
    lancados por rodada, com desempates configuraveis. Lancamentos nao
    CONFIRMADO e lancamentos cuja ficha esta DEPRECADA nunca entram na nota.
    """
    modalidade_id = modalidade.id
    rodada_ids = (
        await db.scalars(select(Rodada.id).where(Rodada.modalidade_id == modalidade_id))
    ).all()

    lancamentos = (
        (
            await db.scalars(
                select(Lancamento)
                .join(Ficha, Lancamento.ficha_id == Ficha.id)
                .where(
                    Lancamento.rodada_id.in_(rodada_ids),
                    Lancamento.status == LancamentoStatus.CONFIRMADO,
                    Ficha.status != FichaStatus.DEPRECADA,
                )
            )
        ).all()
        if rodada_ids
        else []
    )

    melhor_por_equipe_rodada: dict[tuple[UUID, UUID], Lancamento] = {}
    for lancamento in lancamentos:
        chave = (lancamento.equipe_id, lancamento.rodada_id)
        atual = melhor_por_equipe_rodada.get(chave)
        if atual is None or lancamento.total > atual.total:
            melhor_por_equipe_rodada[chave] = lancamento

    lancamentos_por_equipe: dict[UUID, list[Lancamento]] = defaultdict(list)
    for (equipe_id, _rodada_id), lancamento in melhor_por_equipe_rodada.items():
        lancamentos_por_equipe[equipe_id].append(lancamento)

    equipe_ids = await _equipes_inscritas(db, modalidade_id)

    contados_por_equipe: dict[UUID, list[Lancamento]] = {}
    resultados: list[dict] = []
    for equipe_id in equipe_ids:
        candidatos = sorted(
            lancamentos_por_equipe.get(equipe_id, []), key=lambda lanc: lanc.total, reverse=True
        )
        if modalidade.consolidacao == Consolidacao.MELHOR_RODADA:
            contados = candidatos[:1]
        elif modalidade.consolidacao == Consolidacao.MELHOR_N_RODADAS:
            contados = candidatos[: modalidade.consolidacao_n or len(candidatos)]
        elif modalidade.consolidacao == Consolidacao.IGNORA_MENOR_NOTA:
            contados = candidatos[:-1] if len(candidatos) > 1 else candidatos
        else:
            contados = candidatos

        contados_por_equipe[equipe_id] = contados
        nota_final = sum((lanc.total for lanc in contados), Decimal("0"))
        resultados.append(
            {
                "equipe_id": equipe_id,
                "nota_final": nota_final,
                "vitorias": 0,
                "empates": 0,
                "derrotas": 0,
                "eliminado_por_equipe_id": None,
                "formato_chaveamento": None,
            }
        )

    itens_por_lancamento = await _buscar_itens_para_desempate(
        db, contados_por_equipe, modalidade.desempates
    )

    def _chave_desempate(equipe_id: UUID) -> tuple:
        contados = contados_por_equipe[equipe_id]
        chave: list[Decimal] = []
        for regra in modalidade.desempates or []:
            valor = _valor_da_regra(regra, contados, itens_por_lancamento)
            if valor is None:
                continue
            chave.append(-valor if regra["direcao"] == "MAIOR" else valor)
        return tuple(chave)

    niveis_por_equipe = await _equipes_por_nivel(db, modalidade_id)
    return _atribuir_posicoes_por_nivel(
        resultados,
        niveis_por_equipe,
        lambda r: (-r["nota_final"], _chave_desempate(r["equipe_id"])),
    )


async def _buscar_itens_para_desempate(
    db: AsyncSession,
    contados_por_equipe: dict[UUID, list[Lancamento]],
    desempates: list[dict] | None,
) -> dict[UUID, list[LancamentoItem]]:
    if not desempates:
        return {}

    lancamentos = [lanc for contados in contados_por_equipe.values() for lanc in contados]
    if not lancamentos:
        return {}

    revisao_por_lancamento = {lanc.id: lanc.revision for lanc in lancamentos}
    itens = (
        await db.scalars(
            select(LancamentoItem).where(
                LancamentoItem.lancamento_id.in_(revisao_por_lancamento.keys())
            )
        )
    ).all()

    itens_por_lancamento: dict[UUID, list[LancamentoItem]] = defaultdict(list)
    for item in itens:
        if item.revision == revisao_por_lancamento.get(item.lancamento_id):
            itens_por_lancamento[item.lancamento_id].append(item)
    return itens_por_lancamento


def _valor_da_regra(
    regra: dict,
    contados: list[Lancamento],
    itens_por_lancamento: dict[UUID, list[LancamentoItem]],
) -> Decimal | None:
    tipo = regra["tipo"]

    if tipo == "MAIOR_TOTAL_EM_UMA_RODADA":
        return max((lanc.total for lanc in contados), default=Decimal("0"))

    if tipo == "MENOR_TOTAL_PENALIDADES":
        return -sum(
            (
                item.pontos
                for lanc in contados
                for item in itens_por_lancamento.get(lanc.id, [])
                if item.criterio_snapshot.get("categoria") == "PENALIDADE"
            ),
            Decimal("0"),
        )

    if tipo == "MAIOR_PONTUACAO_NO_CRITERIO":
        criterio_id = str(regra.get("criterio_id"))
        return sum(
            (
                item.pontos
                for lanc in contados
                for item in itens_por_lancamento.get(lanc.id, [])
                if str(item.criterio_id) == criterio_id
            ),
            Decimal("0"),
        )

    if tipo == "MENOR_TEMPO":
        if not contados:
            return None
        tempos = [lanc.tempo_gasto_seg for lanc in contados if lanc.tempo_gasto_seg is not None]
        # So decide se TODOS os lancamentos contados tem tempo registrado -
        # comparar equipe com tempo contra equipe sem tempo nao faz sentido
        # (nao da pra saber se a que nao registrou foi mais rapida ou mais
        # lenta), regra e pulada e cai pra proxima.
        if len(tempos) != len(contados):
            return None
        return Decimal(min(tempos))

    # Tipo desconhecido: regra e pulada.
    return None
