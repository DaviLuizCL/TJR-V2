from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.arena import Arena
from app.models.modalidade import TipoDisputa
from app.schemas.arena import ArenaCreate, ArenaUpdate
from app.services.audit import registrar_audit_log
from app.services.modalidade import obter_modalidade


def _validar_niveis_arena(
    niveis_aplicaveis: list[int] | None, niveis_da_modalidade: list[int]
) -> None:
    if niveis_aplicaveis is None:
        return

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

    if not set(niveis_aplicaveis).issubset(set(niveis_da_modalidade)):
        raise AppError(
            codigo="ARENA_NIVEL_FORA_DA_MODALIDADE",
            mensagem="niveis_aplicaveis da arena deve ser um subconjunto dos niveis da modalidade.",
            status_code=422,
        )


def _serializar(arena: Arena) -> dict:
    return {
        "modalidade_id": str(arena.modalidade_id),
        "nome": arena.nome,
        "niveis_aplicaveis": arena.niveis_aplicaveis,
        "ativo": arena.ativo,
    }


async def criar_arena(db: AsyncSession, dto: ArenaCreate, *, usuario_id: UUID) -> Arena:
    modalidade = await obter_modalidade(db, dto.modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.INDIVIDUAL:
        raise AppError(
            codigo="MODALIDADE_NAO_E_INDIVIDUAL",
            mensagem="Arenas so podem ser criadas em modalidades INDIVIDUAL.",
            status_code=422,
        )

    _validar_niveis_arena(dto.niveis_aplicaveis, modalidade.niveis_aplicaveis)

    arena = Arena(
        modalidade_id=dto.modalidade_id,
        nome=dto.nome,
        niveis_aplicaveis=dto.niveis_aplicaveis,
        ativo=dto.ativo,
    )
    db.add(arena)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="arena",
        entidade_id=arena.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(arena),
    )
    return arena


async def obter_arena(db: AsyncSession, arena_id: UUID) -> Arena:
    arena = await db.get(Arena, arena_id)
    if arena is None:
        raise AppError(
            codigo="ARENA_NAO_ENCONTRADA", mensagem="Arena nao encontrada.", status_code=404
        )
    return arena


async def listar_arenas(
    db: AsyncSession,
    *,
    modalidade_id: UUID | None,
    ativo: bool | None,
    page: int,
    size: int,
) -> tuple[list[Arena], int]:
    stmt = select(Arena)
    count_stmt = select(func.count()).select_from(Arena)
    if modalidade_id is not None:
        stmt = stmt.where(Arena.modalidade_id == modalidade_id)
        count_stmt = count_stmt.where(Arena.modalidade_id == modalidade_id)
    if ativo is not None:
        stmt = stmt.where(Arena.ativo == ativo)
        count_stmt = count_stmt.where(Arena.ativo == ativo)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(stmt.order_by(Arena.nome).offset((page - 1) * size).limit(size))
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def atualizar_arena(
    db: AsyncSession, arena_id: UUID, dto: ArenaUpdate, *, usuario_id: UUID
) -> Arena:
    arena = await obter_arena(db, arena_id)
    antes = _serializar(arena)

    dados = dto.model_dump(exclude_unset=True)

    if "niveis_aplicaveis" in dados:
        modalidade = await obter_modalidade(db, arena.modalidade_id)
        _validar_niveis_arena(dados["niveis_aplicaveis"], modalidade.niveis_aplicaveis)

    for campo, valor in dados.items():
        setattr(arena, campo, valor)

    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="arena",
        entidade_id=arena.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(arena),
    )
    return arena
