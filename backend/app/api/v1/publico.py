from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import obter_papel_atual
from app.db.session import get_db
from app.models.usuario import Papel
from app.schemas.publico import EquipeInscritaPublicaOut, ModalidadePublicaOut
from app.services import publico as publico_service

router = APIRouter()


@router.get("/publico/sequencia", response_model=list[ModalidadePublicaOut])
async def obter_sequencia_publica(
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> list[ModalidadePublicaOut]:
    # Aberto pra qualquer papel, inclusive PUBLICO (sem login): nao tem nota.
    sequencia = await publico_service.sequencia_publica(db)
    return [ModalidadePublicaOut.model_validate(m) for m in sequencia]


@router.get("/publico/equipes", response_model=list[EquipeInscritaPublicaOut])
async def listar_equipes_publicas(
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> list[EquipeInscritaPublicaOut]:
    # Aberto pra qualquer papel, inclusive PUBLICO: so nome, nivel e modalidades.
    equipes = await publico_service.equipes_publicas(db)
    return [EquipeInscritaPublicaOut.model_validate(e) for e in equipes]
