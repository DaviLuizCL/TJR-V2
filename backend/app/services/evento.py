from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.evento import Evento, EventoStatus
from app.schemas.evento import EventoCreate, EventoUpdate
from app.services.audit import registrar_audit_log


def _validar_datas(data_inicio: date, data_fim: date) -> None:
    if data_fim < data_inicio:
        raise AppError(
            codigo="DATA_FIM_ANTES_DE_INICIO",
            mensagem="A data de fim nao pode ser anterior a data de inicio.",
            status_code=422,
        )


def _serializar(evento: Evento) -> dict:
    return {
        "nome": evento.nome,
        "ano": evento.ano,
        "data_inicio": evento.data_inicio.isoformat(),
        "data_fim": evento.data_fim.isoformat(),
        "status": evento.status.value,
    }


async def criar_evento(db: AsyncSession, dto: EventoCreate, *, usuario_id: UUID) -> Evento:
    _validar_datas(dto.data_inicio, dto.data_fim)

    evento = Evento(
        nome=dto.nome,
        ano=dto.ano,
        data_inicio=dto.data_inicio,
        data_fim=dto.data_fim,
        status=EventoStatus.RASCUNHO,
    )
    db.add(evento)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="evento",
        entidade_id=evento.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(evento),
    )
    return evento


async def obter_evento(db: AsyncSession, evento_id: UUID) -> Evento:
    evento = await db.get(Evento, evento_id)
    if evento is None:
        raise AppError(
            codigo="EVENTO_NAO_ENCONTRADO", mensagem="Evento nao encontrado.", status_code=404
        )
    return evento


async def listar_eventos(db: AsyncSession, *, page: int, size: int) -> tuple[list[Evento], int]:
    total = await db.scalar(select(func.count()).select_from(Evento))
    resultado = await db.execute(
        select(Evento).order_by(Evento.criado_em.desc()).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def atualizar_evento(
    db: AsyncSession, evento_id: UUID, dto: EventoUpdate, *, usuario_id: UUID
) -> Evento:
    evento = await obter_evento(db, evento_id)
    antes = _serializar(evento)

    dados = dto.model_dump(exclude_unset=True)
    if "data_inicio" in dados or "data_fim" in dados:
        nova_inicio = dados.get("data_inicio", evento.data_inicio)
        nova_fim = dados.get("data_fim", evento.data_fim)
        _validar_datas(nova_inicio, nova_fim)

    for campo, valor in dados.items():
        setattr(evento, campo, valor)

    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="evento",
        entidade_id=evento.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(evento),
    )
    return evento
