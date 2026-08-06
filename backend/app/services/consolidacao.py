from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ficha import Ficha, FichaStatus
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import Consolidacao, FormatoChaveamento, Modalidade, TipoDisputa
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import Rodada
from app.services.modalidade import obter_modalidade


async def calcular_classificacao(db: AsyncSession, modalidade_id: UUID) -> list[dict]:
    """Calcula a classificacao das equipes inscritas numa modalidade.

    Individual: soma/melhor rodada dos totais lancados (comportamento
    original, com desempates configuraveis).

    Confronto + todos-contra-todos: pontos de liga (vitoria/empate/derrota),
    usando `modalidade.pontos_vitoria`/`pontos_empate` (derrota nao pontua).

    Confronto + mata-mata: sem nota, so numero de vitorias e derrotas
    (ordenado por vitorias), e aponta quem eliminou a equipe.
    """
    modalidade = await obter_modalidade(db, modalidade_id)

    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        if modalidade.formato_chaveamento == FormatoChaveamento.MATA_MATA:
            return await _classificacao_bracket(db, modalidade)
        if modalidade.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS:
            return await _classificacao_todos_contra_todos(db, modalidade)

    return await _classificacao_individual(db, modalidade)


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


async def _classificacao_todos_contra_todos(db: AsyncSession, modalidade: Modalidade) -> list[dict]:
    partidas = await _buscar_partidas_decididas(db, modalidade.id)
    equipe_ids = await _equipes_inscritas(db, modalidade.id)

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
            }
        )

    resultados.sort(key=lambda r: -r["nota_final"])
    for posicao, resultado in enumerate(resultados, start=1):
        resultado["posicao"] = posicao
    return resultados


async def _classificacao_bracket(db: AsyncSession, modalidade: Modalidade) -> list[dict]:
    partidas = await _buscar_partidas_decididas(db, modalidade.id)
    equipe_ids = await _equipes_inscritas(db, modalidade.id)

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
            }
        )

    resultados.sort(key=lambda r: (-r["vitorias"], r["derrotas"]))
    for posicao, resultado in enumerate(resultados, start=1):
        resultado["posicao"] = posicao
    return resultados


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

    resultados.sort(key=lambda r: (-r["nota_final"], _chave_desempate(r["equipe_id"])))

    for posicao, resultado in enumerate(resultados, start=1):
        resultado["posicao"] = posicao

    return resultados


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

    # MENOR_TEMPO (ou tipo desconhecido): nao ha campo de tempo hoje, regra e pulada.
    return None
