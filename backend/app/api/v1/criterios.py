from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.criterio import CriterioCreate, CriterioOut, CriterioUpdate
from app.services import criterio as criterio_service

router = APIRouter()


@router.post("/grupos/{grupo_id}/criterios", response_model=CriterioOut, status_code=201)
async def criar_criterio(
    grupo_id: UUID,
    dto: CriterioCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> CriterioOut:
    criterio = await criterio_service.criar_criterio(db, grupo_id, dto, usuario_id=usuario.id)
    return CriterioOut.model_validate(criterio)


@router.patch("/criterios/{criterio_id}", response_model=CriterioOut)
async def atualizar_criterio(
    criterio_id: UUID,
    dto: CriterioUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> CriterioOut:
    criterio = await criterio_service.atualizar_criterio(
        db, criterio_id, dto, usuario_id=usuario.id
    )
    return CriterioOut.model_validate(criterio)


@router.delete("/criterios/{criterio_id}", status_code=204)
async def deletar_criterio(
    criterio_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> None:
    await criterio_service.deletar_criterio(db, criterio_id, usuario_id=usuario.id)
