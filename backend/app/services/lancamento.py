from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.agendamento import Agendamento
from app.models.criterio import Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import Modalidade, TipoDisputa
from app.models.rodada import Rodada
from app.models.usuario import Usuario
from app.schemas.lancamento import (
    ItemLancamentoInput,
    ItemLancamentoOut,
    LancamentoAuditoriaOut,
    LancamentoCorrigir,
    LancamentoCreate,
)
from app.schemas.simulacao import SimulacaoRequest, ValorCriterioSimulado
from app.services import calculo
from app.services.audit import registrar_audit_log
from app.services.chaveamento import registrar_resultado_lancamento
from app.services.equipe import obter_equipe
from app.services.ficha import obter_ficha_completa
from app.services.modalidade import obter_modalidade
from app.services.rodada import obter_rodada


def _criterios_por_id(ficha) -> dict[UUID, Criterio]:
    return {c.id: c for grupo in ficha.grupos for c in grupo.criterios}


def _snapshot_criterio(criterio: Criterio) -> dict:
    return {
        "nome": criterio.nome,
        "categoria": criterio.categoria.value,
        "tipo": criterio.tipo.value,
        "pontos": float(criterio.pontos) if criterio.pontos is not None else None,
        "valores_permitidos": criterio.valores_permitidos,
        "max_ocorrencias": criterio.max_ocorrencias,
        "modificador_tipo": criterio.modificador_tipo.value if criterio.modificador_tipo else None,
        "modificador_valor": (
            float(criterio.modificador_valor) if criterio.modificador_valor is not None else None
        ),
    }


def _serializar(lancamento: Lancamento) -> dict:
    return {
        "ficha_id": str(lancamento.ficha_id),
        "rodada_id": str(lancamento.rodada_id),
        "equipe_id": str(lancamento.equipe_id),
        "tentativa": lancamento.tentativa,
        "revision": lancamento.revision,
        "status": lancamento.status.value,
        "total": float(lancamento.total),
    }


async def _listar_itens_da_revisao(
    db: AsyncSession, lancamento_id: UUID, revision: int
) -> list[LancamentoItem]:
    resultado = await db.execute(
        select(LancamentoItem)
        .where(LancamentoItem.lancamento_id == lancamento_id, LancamentoItem.revision == revision)
        .order_by(LancamentoItem.criado_em)
    )
    return list(resultado.scalars().all())


async def _gravar_itens(
    db: AsyncSession,
    lancamento_id: UUID,
    revision: int,
    itens: list[ItemLancamentoInput],
    criterios_por_id: dict[UUID, Criterio],
    resultado_calculo,
) -> None:
    """Grava uma nova geracao de itens para a `revision` informada.

    Nunca apaga ou sobrescreve itens de revisoes anteriores (regra invioravel
    5: nada de DELETE em dado de pontuacao) - cada correcao de lancamento
    soma uma nova revision, preservando o rastro completo.
    """
    detalhe_por_id = {d.criterio_id: d for d in resultado_calculo.detalhamento_por_criterio}

    for item_in in itens:
        criterio = criterios_por_id[item_in.criterio_id]
        snapshot = _snapshot_criterio(criterio)

        if criterio.tipo == CriterioTipo.MODIFICADOR:
            snapshot["aplicado"] = bool(item_in.aplicado)
            item = LancamentoItem(
                lancamento_id=lancamento_id,
                criterio_id=criterio.id,
                criterio_snapshot=snapshot,
                ocorrencias=None,
                valor=None,
                pontos=0,
                revision=revision,
            )
        elif criterio.tipo == CriterioTipo.ESCALA:
            detalhe = detalhe_por_id[criterio.id]
            item = LancamentoItem(
                lancamento_id=lancamento_id,
                criterio_id=criterio.id,
                criterio_snapshot=snapshot,
                ocorrencias=None,
                valor=item_in.valor,
                pontos=detalhe.pontos,
                revision=revision,
            )
        else:
            detalhe = detalhe_por_id[criterio.id]
            item = LancamentoItem(
                lancamento_id=lancamento_id,
                criterio_id=criterio.id,
                criterio_snapshot=snapshot,
                ocorrencias=item_in.ocorrencias or 0,
                valor=None,
                pontos=detalhe.pontos,
                revision=revision,
            )
        db.add(item)

    await db.flush()


def _validar_itens_pertencem_a_ficha(
    itens: list[ItemLancamentoInput], criterios_por_id: dict[UUID, Criterio]
) -> None:
    for item_in in itens:
        if item_in.criterio_id not in criterios_por_id:
            raise AppError(
                codigo="CRITERIO_NAO_PERTENCE_A_FICHA",
                mensagem=f"Criterio {item_in.criterio_id} nao pertence a esta ficha.",
                status_code=422,
            )


def _validar_campo_aplicado(
    itens: list[ItemLancamentoInput], criterios_por_id: dict[UUID, Criterio]
) -> None:
    """O campo `aplicado` so faz sentido para MODIFICADOR (o unico tipo que o
    servico de calculo le). Mandar `aplicado` num criterio de outro tipo nao
    da erro nenhum hoje -- so e silenciosamente ignorado, e como o campo
    `ocorrencias` fica ausente, o item vira 0 sem avisar ninguem.
    """
    for item_in in itens:
        criterio = criterios_por_id[item_in.criterio_id]
        if criterio.tipo != CriterioTipo.MODIFICADOR and item_in.aplicado is not None:
            raise AppError(
                codigo="CAMPO_APLICADO_INVALIDO_PARA_CRITERIO",
                mensagem=(
                    f"O campo 'aplicado' so e valido para criterios do tipo MODIFICADOR; "
                    f"'{criterio.nome}' e do tipo {criterio.tipo.value}."
                ),
                status_code=422,
                detalhes={"criterio_id": str(criterio.id)},
            )


async def lancamento_existe_por_operacao(db: AsyncSession, client_operation_id: UUID) -> bool:
    existente = await db.scalar(
        select(Lancamento.id).where(Lancamento.client_operation_id == client_operation_id)
    )
    return existente is not None


async def criar_lancamento(
    db: AsyncSession, dto: LancamentoCreate, *, arbitro_id: UUID
) -> Lancamento:
    existente = await db.scalar(
        select(Lancamento).where(Lancamento.client_operation_id == dto.client_operation_id)
    )
    if existente is not None:
        return existente

    ficha = await obter_ficha_completa(db, dto.ficha_id)
    modalidade = await obter_modalidade(db, ficha.modalidade_id)
    rodada = await obter_rodada(db, dto.rodada_id)
    if rodada.modalidade_id != modalidade.id:
        raise AppError(
            codigo="RODADA_INCOMPATIVEL_COM_FICHA",
            mensagem="A rodada informada nao pertence a modalidade desta ficha.",
            status_code=422,
        )
    await obter_equipe(db, dto.equipe_id)

    duplicado = await db.scalar(
        select(Lancamento).where(
            Lancamento.rodada_id == dto.rodada_id,
            Lancamento.equipe_id == dto.equipe_id,
            Lancamento.tentativa == dto.tentativa,
            Lancamento.status != LancamentoStatus.ANULADO,
        )
    )
    if duplicado is not None:
        raise AppError(
            codigo="LANCAMENTO_JA_EXISTE",
            mensagem=(
                "Ja existe um lancamento para esta equipe, rodada e tentativa. "
                "Corrija o lancamento existente em vez de criar um novo."
            ),
            status_code=409,
            detalhes={"lancamento_id": str(duplicado.id)},
        )

    if modalidade.tipo_disputa == TipoDisputa.INDIVIDUAL:
        agendamento = await db.scalar(
            select(Agendamento).where(
                Agendamento.rodada_id == dto.rodada_id, Agendamento.equipe_id == dto.equipe_id
            )
        )
        if agendamento is None:
            raise AppError(
                codigo="EQUIPE_SEM_ARENA_ATRIBUIDA",
                mensagem=(
                    "Esta equipe nao tem arena atribuida para esta rodada. "
                    "Gere o horario da modalidade antes de lancar pontuacao."
                ),
                status_code=422,
            )

    criterios_por_id = _criterios_por_id(ficha)
    _validar_itens_pertencem_a_ficha(dto.itens, criterios_por_id)
    _validar_campo_aplicado(dto.itens, criterios_por_id)

    valores = [
        ValorCriterioSimulado(
            criterio_id=item.criterio_id,
            ocorrencias=item.ocorrencias,
            valor=item.valor,
            aplicado=item.aplicado,
        )
        for item in dto.itens
    ]
    resultado_calculo = calculo.calcular(ficha, modalidade, SimulacaoRequest(valores=valores))

    lancamento = Lancamento(
        ficha_id=dto.ficha_id,
        rodada_id=dto.rodada_id,
        tentativa=dto.tentativa,
        equipe_id=dto.equipe_id,
        partida_id=dto.partida_id,
        arbitro_id=arbitro_id,
        client_operation_id=dto.client_operation_id,
        revision=1,
        status=LancamentoStatus.PENDENTE,
        total=resultado_calculo.total,
    )
    db.add(lancamento)
    await db.flush()

    await _gravar_itens(
        db, lancamento.id, lancamento.revision, dto.itens, criterios_por_id, resultado_calculo
    )

    await registrar_audit_log(
        db,
        usuario_id=arbitro_id,
        entidade="lancamento",
        entidade_id=lancamento.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(lancamento),
    )
    return lancamento


async def obter_lancamento(db: AsyncSession, lancamento_id: UUID) -> Lancamento:
    lancamento = await db.get(Lancamento, lancamento_id)
    if lancamento is None:
        raise AppError(
            codigo="LANCAMENTO_NAO_ENCONTRADO",
            mensagem="Lancamento nao encontrado.",
            status_code=404,
        )
    return lancamento


async def obter_lancamento_completo(db: AsyncSession, lancamento_id: UUID) -> Lancamento:
    lancamento = await obter_lancamento(db, lancamento_id)
    lancamento.itens = await _listar_itens_da_revisao(db, lancamento.id, lancamento.revision)
    return lancamento


async def listar_lancamentos(
    db: AsyncSession,
    *,
    rodada_id: UUID | None,
    equipe_id: UUID | None,
    page: int,
    size: int,
) -> tuple[list[Lancamento], int]:
    stmt = select(Lancamento)
    count_stmt = select(func.count()).select_from(Lancamento)
    if rodada_id is not None:
        stmt = stmt.where(Lancamento.rodada_id == rodada_id)
        count_stmt = count_stmt.where(Lancamento.rodada_id == rodada_id)
    if equipe_id is not None:
        stmt = stmt.where(Lancamento.equipe_id == equipe_id)
        count_stmt = count_stmt.where(Lancamento.equipe_id == equipe_id)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(
        stmt.order_by(Lancamento.criado_em.desc()).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def confirmar_lancamento(
    db: AsyncSession, lancamento_id: UUID, *, usuario_id: UUID
) -> Lancamento:
    lancamento = await obter_lancamento(db, lancamento_id)
    if lancamento.status != LancamentoStatus.PENDENTE:
        raise AppError(
            codigo="LANCAMENTO_NAO_PENDENTE",
            mensagem="Somente um lancamento PENDENTE pode ser confirmado.",
            status_code=422,
        )

    antes = _serializar(lancamento)
    lancamento.status = LancamentoStatus.CONFIRMADO
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="lancamento",
        entidade_id=lancamento.id,
        acao="CONFIRMAR",
        antes=antes,
        depois=_serializar(lancamento),
    )

    await registrar_resultado_lancamento(db, lancamento, usuario_id=usuario_id)
    return lancamento


async def corrigir_lancamento(
    db: AsyncSession, lancamento_id: UUID, dto: LancamentoCorrigir, *, usuario_id: UUID
) -> Lancamento:
    if not dto.justificativa.strip():
        raise AppError(
            codigo="JUSTIFICATIVA_OBRIGATORIA",
            mensagem="Toda correcao de lancamento exige justificativa.",
            status_code=422,
        )

    lancamento = await obter_lancamento(db, lancamento_id)
    if lancamento.status != LancamentoStatus.CONFIRMADO:
        raise AppError(
            codigo="LANCAMENTO_NAO_CONFIRMADO",
            mensagem="Somente um lancamento CONFIRMADO pode ser corrigido.",
            status_code=422,
        )
    if dto.revision != lancamento.revision:
        raise AppError(
            codigo="LANCAMENTO_REVISION_DESATUALIZADA",
            mensagem=(
                "Este lancamento foi alterado por outra correcao desde que voce o abriu. "
                "Recarregue o estado atual antes de corrigir de novo."
            ),
            status_code=409,
            detalhes={"revision_atual": lancamento.revision, "lancamento": _serializar(lancamento)},
        )
    itens_atuais = await _listar_itens_da_revisao(db, lancamento.id, lancamento.revision)
    criterios_atuais = {item.criterio_id for item in itens_atuais}
    criterios_corrigidos = {item.criterio_id for item in dto.itens}
    criterios_faltando = criterios_atuais - criterios_corrigidos
    if criterios_faltando:
        raise AppError(
            codigo="CORRECAO_OMITE_CRITERIO",
            mensagem=(
                "A correcao precisa incluir todos os criterios que o lancamento original "
                "tinha, mesmo que o valor nao mude. Para zerar um criterio, envie-o "
                "explicitamente com ocorrencias/valor zero."
            ),
            status_code=422,
            detalhes={"criterios_faltando": [str(c) for c in criterios_faltando]},
        )

    antes = _serializar(lancamento)

    ficha = await obter_ficha_completa(db, lancamento.ficha_id)
    modalidade = await obter_modalidade(db, ficha.modalidade_id)

    criterios_por_id = _criterios_por_id(ficha)
    _validar_itens_pertencem_a_ficha(dto.itens, criterios_por_id)
    _validar_campo_aplicado(dto.itens, criterios_por_id)

    valores = [
        ValorCriterioSimulado(
            criterio_id=item.criterio_id,
            ocorrencias=item.ocorrencias,
            valor=item.valor,
            aplicado=item.aplicado,
        )
        for item in dto.itens
    ]
    resultado_calculo = calculo.calcular(ficha, modalidade, SimulacaoRequest(valores=valores))

    nova_revision = lancamento.revision + 1
    await _gravar_itens(
        db, lancamento.id, nova_revision, dto.itens, criterios_por_id, resultado_calculo
    )

    lancamento.total = resultado_calculo.total
    lancamento.revision = nova_revision
    lancamento.status = LancamentoStatus.CONFIRMADO
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="lancamento",
        entidade_id=lancamento.id,
        acao="CORRIGIR",
        antes=antes,
        depois=_serializar(lancamento),
        justificativa=dto.justificativa,
    )

    await registrar_resultado_lancamento(db, lancamento, usuario_id=usuario_id)
    return lancamento


async def listar_lancamentos_auditoria(
    db: AsyncSession,
    *,
    evento_id: UUID | None = None,
    modalidade_id: UUID | None = None,
    rodada_id: UUID | None = None,
    equipe_id: UUID | None = None,
    page: int,
    size: int,
) -> tuple[list[LancamentoAuditoriaOut], int]:
    """Lista lancamentos com dados enriquecidos (modalidade, nivel, equipe,
    arbitro) para o painel de auditoria: conferir se as somas e subtracoes da
    ficha bateram, na hora, sem precisar abrir cada lancamento.

    Todos os filtros sao opcionais e combinaveis. `equipe_id` nao exige
    `evento_id` (equipe nao pertence a um evento especifico) -- usado pela
    tela "Submissoes" de uma equipe, que lista o historico dela em qualquer
    modalidade/evento em que esteja inscrita.
    """
    joins = (
        select(Lancamento, Modalidade.nome, Equipe.nivel, Equipe.nome, Rodada.numero, Usuario.nome)
        .join(Rodada, Lancamento.rodada_id == Rodada.id)
        .join(Modalidade, Rodada.modalidade_id == Modalidade.id)
        .join(Equipe, Lancamento.equipe_id == Equipe.id)
        .join(Usuario, Lancamento.arbitro_id == Usuario.id)
    )
    count_stmt = (
        select(func.count())
        .select_from(Lancamento)
        .join(Rodada, Lancamento.rodada_id == Rodada.id)
        .join(Modalidade, Rodada.modalidade_id == Modalidade.id)
    )
    if evento_id is not None:
        joins = joins.where(Modalidade.evento_id == evento_id)
        count_stmt = count_stmt.where(Modalidade.evento_id == evento_id)
    if modalidade_id is not None:
        joins = joins.where(Modalidade.id == modalidade_id)
        count_stmt = count_stmt.where(Modalidade.id == modalidade_id)
    if rodada_id is not None:
        joins = joins.where(Rodada.id == rodada_id)
        count_stmt = count_stmt.where(Rodada.id == rodada_id)
    if equipe_id is not None:
        joins = joins.where(Lancamento.equipe_id == equipe_id)
        count_stmt = count_stmt.where(Lancamento.equipe_id == equipe_id)

    total = await db.scalar(count_stmt)

    resultado = await db.execute(
        joins.order_by(Lancamento.criado_em.desc()).offset((page - 1) * size).limit(size)
    )
    linhas = resultado.all()

    revisao_por_lancamento = {linha[0].id: linha[0].revision for linha in linhas}
    itens_por_lancamento: dict[UUID, list[LancamentoItem]] = {}
    if revisao_por_lancamento:
        itens_resultado = await db.execute(
            select(LancamentoItem).where(
                LancamentoItem.lancamento_id.in_(revisao_por_lancamento.keys())
            )
        )
        for item in itens_resultado.scalars().all():
            if item.revision == revisao_por_lancamento.get(item.lancamento_id):
                itens_por_lancamento.setdefault(item.lancamento_id, []).append(item)

    auditorias = []
    for linha in linhas:
        lancamento, modalidade_nome, nivel_equipe, equipe_nome, rodada_numero, arbitro_nome = linha
        auditorias.append(
            LancamentoAuditoriaOut(
                id=lancamento.id,
                modalidade_nome=modalidade_nome,
                nivel=nivel_equipe,
                equipe_nome=equipe_nome,
                rodada_numero=rodada_numero,
                tentativa=lancamento.tentativa,
                responsavel_nome=arbitro_nome,
                horario_submissao=lancamento.criado_em,
                status=lancamento.status,
                total=float(lancamento.total),
                itens=[
                    ItemLancamentoOut.model_validate(item)
                    for item in itens_por_lancamento.get(lancamento.id, [])
                ],
            )
        )
    return auditorias, total or 0
