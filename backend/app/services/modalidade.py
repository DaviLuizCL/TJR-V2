from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.schemas.modalidade import ModalidadeCreate, ModalidadeUpdate
from app.services.audit import registrar_audit_log
from app.services.evento import obter_evento

_TIPOS_DESEMPATE = {
    "MAIOR_TOTAL_EM_UMA_RODADA",
    "MENOR_TOTAL_PENALIDADES",
    "MAIOR_PONTUACAO_NO_CRITERIO",
    "MENOR_TEMPO",
}
_DIRECOES_DESEMPATE = {"MAIOR", "MENOR"}


def _validar_niveis_aplicaveis(niveis_aplicaveis: list[int]) -> None:
    valido = (
        bool(niveis_aplicaveis)
        and len(set(niveis_aplicaveis)) == len(niveis_aplicaveis)
        and all(1 <= n <= 4 for n in niveis_aplicaveis)
    )
    if not valido:
        raise AppError(
            codigo="NIVEIS_APLICAVEIS_INVALIDOS",
            mensagem="niveis_aplicaveis deve conter valores unicos entre 1 e 4.",
            status_code=422,
        )


def _validar_desempates(desempates: list[dict] | None) -> None:
    if not desempates:
        return

    for item in desempates:
        if not isinstance(item, dict):
            raise AppError(
                codigo="DESEMPATE_INVALIDO",
                mensagem="Cada regra de desempate deve ser um objeto.",
                status_code=422,
            )

        tipo = item.get("tipo")
        direcao = item.get("direcao")
        criterio_id = item.get("criterio_id")

        if tipo not in _TIPOS_DESEMPATE:
            raise AppError(
                codigo="DESEMPATE_INVALIDO",
                mensagem=f"tipo de desempate invalido: {tipo!r}",
                status_code=422,
            )
        if direcao not in _DIRECOES_DESEMPATE:
            raise AppError(
                codigo="DESEMPATE_INVALIDO",
                mensagem=f"direcao de desempate invalida: {direcao!r}",
                status_code=422,
            )

        exige_criterio = tipo == "MAIOR_PONTUACAO_NO_CRITERIO"
        if exige_criterio and not criterio_id:
            raise AppError(
                codigo="DESEMPATE_INVALIDO",
                mensagem="criterio_id e obrigatorio para MAIOR_PONTUACAO_NO_CRITERIO.",
                status_code=422,
            )
        if not exige_criterio and criterio_id:
            raise AppError(
                codigo="DESEMPATE_INVALIDO",
                mensagem="criterio_id so e permitido para MAIOR_PONTUACAO_NO_CRITERIO.",
                status_code=422,
            )


def _validar_regras(
    *,
    tipo_disputa: TipoDisputa,
    formato_chaveamento: FormatoChaveamento | None,
    niveis_aplicaveis: list[int],
    qtd_rodadas: int,
    consolidacao: Consolidacao,
    consolidacao_n: int | None,
    desempates: list[dict] | None,
) -> None:
    _validar_niveis_aplicaveis(niveis_aplicaveis)

    if formato_chaveamento is not None and tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="FORMATO_CHAVEAMENTO_APENAS_CONFRONTO",
            mensagem="formato_chaveamento so pode ser definido quando tipo_disputa e CONFRONTO.",
            status_code=422,
        )

    if consolidacao == Consolidacao.MELHOR_N_RODADAS:
        if consolidacao_n is None:
            raise AppError(
                codigo="CONSOLIDACAO_N_OBRIGATORIO",
                mensagem="consolidacao_n e obrigatorio quando consolidacao e MELHOR_N_RODADAS.",
                status_code=422,
            )
        if consolidacao_n > qtd_rodadas:
            raise AppError(
                codigo="CONSOLIDACAO_N_MAIOR_QUE_QTD_RODADAS",
                mensagem="consolidacao_n nao pode ser maior que qtd_rodadas.",
                status_code=422,
            )

    _validar_desempates(desempates)


def _serializar(modalidade: Modalidade) -> dict:
    return {
        "nome": modalidade.nome,
        "descricao": modalidade.descricao,
        "tipo_disputa": modalidade.tipo_disputa.value,
        "formato_chaveamento": (
            modalidade.formato_chaveamento.value if modalidade.formato_chaveamento else None
        ),
        "niveis_aplicaveis": modalidade.niveis_aplicaveis,
        "ficha_unica_entre_niveis": modalidade.ficha_unica_entre_niveis,
        "qtd_rodadas": modalidade.qtd_rodadas,
        "tentativas_por_rodada": modalidade.tentativas_por_rodada,
        "duracao_maxima_rodada_seg": modalidade.duracao_maxima_rodada_seg,
        "pausa_entre_rodadas_seg": modalidade.pausa_entre_rodadas_seg,
        "consolidacao": modalidade.consolidacao.value,
        "consolidacao_n": modalidade.consolidacao_n,
        "permite_total_negativo": modalidade.permite_total_negativo,
        "desempates": modalidade.desempates,
        "pontos_vitoria": float(modalidade.pontos_vitoria),
        "pontos_empate": float(modalidade.pontos_empate),
        "status": modalidade.status.value,
        "ranking_liberado": modalidade.ranking_liberado,
    }


async def criar_modalidade(
    db: AsyncSession, dto: ModalidadeCreate, *, usuario_id: UUID
) -> Modalidade:
    await obter_evento(db, dto.evento_id)

    _validar_regras(
        tipo_disputa=dto.tipo_disputa,
        formato_chaveamento=dto.formato_chaveamento,
        niveis_aplicaveis=dto.niveis_aplicaveis,
        qtd_rodadas=dto.qtd_rodadas,
        consolidacao=dto.consolidacao,
        consolidacao_n=dto.consolidacao_n,
        desempates=dto.desempates,
    )

    modalidade = Modalidade(
        evento_id=dto.evento_id,
        nome=dto.nome,
        descricao=dto.descricao,
        tipo_disputa=dto.tipo_disputa,
        formato_chaveamento=dto.formato_chaveamento,
        niveis_aplicaveis=dto.niveis_aplicaveis,
        ficha_unica_entre_niveis=dto.ficha_unica_entre_niveis,
        qtd_rodadas=dto.qtd_rodadas,
        tentativas_por_rodada=dto.tentativas_por_rodada,
        duracao_maxima_rodada_seg=dto.duracao_maxima_rodada_seg,
        pausa_entre_rodadas_seg=dto.pausa_entre_rodadas_seg,
        consolidacao=dto.consolidacao,
        consolidacao_n=dto.consolidacao_n,
        permite_total_negativo=dto.permite_total_negativo,
        desempates=dto.desempates,
        pontos_vitoria=dto.pontos_vitoria,
        pontos_empate=dto.pontos_empate,
        status=ModalidadeStatus.RASCUNHO,
    )
    db.add(modalidade)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(modalidade),
    )
    return modalidade


async def obter_modalidade(db: AsyncSession, modalidade_id: UUID) -> Modalidade:
    modalidade = await db.get(Modalidade, modalidade_id)
    if modalidade is None:
        raise AppError(
            codigo="MODALIDADE_NAO_ENCONTRADA",
            mensagem="Modalidade nao encontrada.",
            status_code=404,
        )
    return modalidade


async def listar_modalidades(
    db: AsyncSession, *, evento_id: UUID | None, page: int, size: int
) -> tuple[list[Modalidade], int]:
    stmt = select(Modalidade)
    count_stmt = select(func.count()).select_from(Modalidade)
    if evento_id is not None:
        stmt = stmt.where(Modalidade.evento_id == evento_id)
        count_stmt = count_stmt.where(Modalidade.evento_id == evento_id)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(
        stmt.order_by(Modalidade.criado_em.desc()).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def atualizar_modalidade(
    db: AsyncSession, modalidade_id: UUID, dto: ModalidadeUpdate, *, usuario_id: UUID
) -> Modalidade:
    modalidade = await obter_modalidade(db, modalidade_id)
    antes = _serializar(modalidade)

    dados = dto.model_dump(exclude_unset=True)

    _validar_regras(
        tipo_disputa=dados.get("tipo_disputa", modalidade.tipo_disputa),
        formato_chaveamento=dados.get("formato_chaveamento", modalidade.formato_chaveamento),
        niveis_aplicaveis=dados.get("niveis_aplicaveis", modalidade.niveis_aplicaveis),
        qtd_rodadas=dados.get("qtd_rodadas", modalidade.qtd_rodadas),
        consolidacao=dados.get("consolidacao", modalidade.consolidacao),
        consolidacao_n=dados.get("consolidacao_n", modalidade.consolidacao_n),
        desempates=dados.get("desempates", modalidade.desempates),
    )

    for campo, valor in dados.items():
        setattr(modalidade, campo, valor)

    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(modalidade),
    )
    return modalidade
