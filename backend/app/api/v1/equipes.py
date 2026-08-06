from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.equipe import EquipeCreate, EquipeOut, EquipeUpdate
from app.services import equipe as equipe_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/equipes", response_model=EquipeOut, status_code=201)
async def criar_equipe(
    dto: EquipeCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> EquipeOut:
    equipe = await equipe_service.criar_equipe(db, dto, usuario_id=usuario.id)
    return EquipeOut.model_validate(equipe)


@router.get("/equipes", response_model=Pagina[EquipeOut])
async def listar_equipes(
    nivel: int | None = None,
    ativo: bool | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[EquipeOut]:
    itens, total = await equipe_service.listar_equipes(
        db, nivel=nivel, ativo=ativo, page=page, size=size
    )
    return Pagina(
        itens=[EquipeOut.model_validate(item) for item in itens], total=total, page=page, size=size
    )


@router.get("/equipes/{equipe_id}", response_model=EquipeOut)
async def obter_equipe(
    equipe_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> EquipeOut:
    equipe = await equipe_service.obter_equipe(db, equipe_id)
    return EquipeOut.model_validate(equipe)


@router.patch("/equipes/{equipe_id}", response_model=EquipeOut)
async def atualizar_equipe(
    equipe_id: UUID,
    dto: EquipeUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> EquipeOut:
    equipe = await equipe_service.atualizar_equipe(db, equipe_id, dto, usuario_id=usuario.id)
    return EquipeOut.model_validate(equipe)
