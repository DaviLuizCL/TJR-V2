from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.inscricao import Inscricao
from app.schemas.inscricao import InscricaoCreate
from app.services.audit import registrar_audit_log
from app.services.equipe import obter_equipe
from app.services.modalidade import obter_modalidade


def _serializar(inscricao: Inscricao) -> dict:
    return {
        "equipe_id": str(inscricao.equipe_id),
        "modalidade_id": str(inscricao.modalidade_id),
    }


async def criar_inscricao(db: AsyncSession, dto: InscricaoCreate, *, usuario_id: UUID) -> Inscricao:
    equipe = await obter_equipe(db, dto.equipe_id)
    modalidade = await obter_modalidade(db, dto.modalidade_id)

    if equipe.nivel not in modalidade.niveis_aplicaveis:
        raise AppError(
            codigo="NIVEL_EQUIPE_INCOMPATIVEL",
            mensagem="O nivel da equipe nao e aplicavel a esta modalidade.",
            status_code=422,
        )

    existente = await db.scalar(
        select(Inscricao).where(
            Inscricao.equipe_id == equipe.id, Inscricao.modalidade_id == modalidade.id
        )
    )
    if existente is not None:
        raise AppError(
            codigo="INSCRICAO_DUPLICADA",
            mensagem="Esta equipe ja esta inscrita nesta modalidade.",
            status_code=409,
        )

    inscricao = Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id)
    db.add(inscricao)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="inscricao",
        entidade_id=inscricao.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(inscricao),
    )
    return inscricao


async def obter_inscricao(db: AsyncSession, inscricao_id: UUID) -> Inscricao:
    inscricao = await db.get(Inscricao, inscricao_id)
    if inscricao is None:
        raise AppError(
            codigo="INSCRICAO_NAO_ENCONTRADA",
            mensagem="Inscricao nao encontrada.",
            status_code=404,
        )
    return inscricao


async def listar_inscricoes(
    db: AsyncSession,
    *,
    modalidade_id: UUID | None,
    equipe_id: UUID | None,
    page: int,
    size: int,
) -> tuple[list[Inscricao], int]:
    stmt = select(Inscricao)
    count_stmt = select(func.count()).select_from(Inscricao)
    if modalidade_id is not None:
        stmt = stmt.where(Inscricao.modalidade_id == modalidade_id)
        count_stmt = count_stmt.where(Inscricao.modalidade_id == modalidade_id)
    if equipe_id is not None:
        stmt = stmt.where(Inscricao.equipe_id == equipe_id)
        count_stmt = count_stmt.where(Inscricao.equipe_id == equipe_id)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(
        stmt.order_by(Inscricao.criado_em.desc()).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def deletar_inscricao(db: AsyncSession, inscricao_id: UUID, *, usuario_id: UUID) -> None:
    inscricao = await obter_inscricao(db, inscricao_id)
    antes = _serializar(inscricao)

    await db.delete(inscricao)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="inscricao",
        entidade_id=inscricao.id,
        acao="DELETAR",
        antes=antes,
        depois=None,
    )
