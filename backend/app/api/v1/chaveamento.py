from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.chaveamento import GerarChaveamentoRequest
from app.schemas.rodada import RodadaOut
from app.services import chaveamento as chaveamento_service

router = APIRouter()


@router.post("/chaveamento/gerar", response_model=RodadaOut, status_code=201)
async def gerar_chaveamento(
    dto: GerarChaveamentoRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> RodadaOut:
    rodada = await chaveamento_service.gerar_chaveamento_inicial(
        db, dto.modalidade_id, usuario_id=usuario.id
    )
    return RodadaOut.model_validate(rodada)
