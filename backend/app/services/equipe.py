from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.schemas.equipe import EquipeCreate, EquipeUpdate
from app.services.audit import registrar_audit_log


def _serializar(equipe: Equipe) -> dict:
    return {"nome": equipe.nome, "nivel": equipe.nivel, "ativo": equipe.ativo}


async def criar_equipe(db: AsyncSession, dto: EquipeCreate, *, usuario_id: UUID) -> Equipe:
    equipe = Equipe(nome=dto.nome, nivel=dto.nivel, ativo=dto.ativo)
    db.add(equipe)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="equipe",
        entidade_id=equipe.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(equipe),
    )
    return equipe


async def obter_equipe(db: AsyncSession, equipe_id: UUID) -> Equipe:
    equipe = await db.get(Equipe, equipe_id)
    if equipe is None:
        raise AppError(
            codigo="EQUIPE_NAO_ENCONTRADA", mensagem="Equipe nao encontrada.", status_code=404
        )
    return equipe


async def listar_equipes(
    db: AsyncSession,
    *,
    nivel: int | None,
    ativo: bool | None,
    modalidade_id: UUID | None = None,
    page: int,
    size: int,
) -> tuple[list[Equipe], int]:
    stmt = select(Equipe)
    count_stmt = select(func.count()).select_from(Equipe)
    if nivel is not None:
        stmt = stmt.where(Equipe.nivel == nivel)
        count_stmt = count_stmt.where(Equipe.nivel == nivel)
    if ativo is not None:
        stmt = stmt.where(Equipe.ativo == ativo)
        count_stmt = count_stmt.where(Equipe.ativo == ativo)
    if modalidade_id is not None:
        subquery = select(Inscricao.equipe_id).where(Inscricao.modalidade_id == modalidade_id)
        stmt = stmt.where(Equipe.id.in_(subquery))
        count_stmt = count_stmt.where(Equipe.id.in_(subquery))

    total = await db.scalar(count_stmt)
    resultado = await db.execute(stmt.order_by(Equipe.nome).offset((page - 1) * size).limit(size))
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def atualizar_equipe(
    db: AsyncSession, equipe_id: UUID, dto: EquipeUpdate, *, usuario_id: UUID
) -> Equipe:
    equipe = await obter_equipe(db, equipe_id)
    antes = _serializar(equipe)

    dados = dto.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(equipe, campo, valor)

    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="equipe",
        entidade_id=equipe.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(equipe),
    )
    return equipe
