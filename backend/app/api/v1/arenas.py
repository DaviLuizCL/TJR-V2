from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.arena import ArenaCreate, ArenaOut, ArenaUpdate
from app.schemas.common import Pagina
from app.services import arena as arena_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/arenas", response_model=ArenaOut, status_code=201)
async def criar_arena(
    dto: ArenaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> ArenaOut:
    arena = await arena_service.criar_arena(db, dto, usuario_id=usuario.id)
    return ArenaOut.model_validate(arena)


@router.get("/arenas", response_model=Pagina[ArenaOut])
async def listar_arenas(
    modalidade_id: UUID | None = None,
    ativo: bool | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[ArenaOut]:
    itens, total = await arena_service.listar_arenas(
        db, modalidade_id=modalidade_id, ativo=ativo, page=page, size=size
    )
    return Pagina(
        itens=[ArenaOut.model_validate(item) for item in itens], total=total, page=page, size=size
    )


@router.get("/arenas/{arena_id}", response_model=ArenaOut)
async def obter_arena(
    arena_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> ArenaOut:
    arena = await arena_service.obter_arena(db, arena_id)
    return ArenaOut.model_validate(arena)


@router.patch("/arenas/{arena_id}", response_model=ArenaOut)
async def atualizar_arena(
    arena_id: UUID,
    dto: ArenaUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> ArenaOut:
    arena = await arena_service.atualizar_arena(db, arena_id, dto, usuario_id=usuario.id)
    return ArenaOut.model_validate(arena)
