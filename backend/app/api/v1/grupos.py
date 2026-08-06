from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.grupo import GrupoCreate, GrupoOut, GrupoUpdate
from app.services import grupo as grupo_service

router = APIRouter()


@router.post("/fichas/{ficha_id}/grupos", response_model=GrupoOut, status_code=201)
async def criar_grupo(
    ficha_id: UUID,
    dto: GrupoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> GrupoOut:
    grupo = await grupo_service.criar_grupo(db, ficha_id, dto, usuario_id=usuario.id)
    grupo.criterios = []
    return GrupoOut.model_validate(grupo)


@router.patch("/grupos/{grupo_id}", response_model=GrupoOut)
async def atualizar_grupo(
    grupo_id: UUID,
    dto: GrupoUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> GrupoOut:
    grupo = await grupo_service.atualizar_grupo(db, grupo_id, dto, usuario_id=usuario.id)
    grupo.criterios = []
    return GrupoOut.model_validate(grupo)


@router.delete("/grupos/{grupo_id}", status_code=204)
async def deletar_grupo(
    grupo_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> None:
    await grupo_service.deletar_grupo(db, grupo_id, usuario_id=usuario.id)
