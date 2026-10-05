from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.chaveamento import (
    CriarPartidaManualRequest,
    ResetarChaveamentoRequest,
)
from app.schemas.partida import PartidaOut
from app.services import chaveamento as chaveamento_service

router = APIRouter()


@router.post(
    "/modalidades/{modalidade_id}/chaveamento/partida-manual",
    response_model=PartidaOut,
    status_code=201,
)
async def criar_partida_manual(
    modalidade_id: UUID,
    dto: CriarPartidaManualRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> PartidaOut:
    partida = await chaveamento_service.criar_partida_manual(
        db,
        modalidade_id,
        dto.equipe_a_id,
        dto.equipe_b_id,
        rodada_numero=dto.rodada_numero,
        formato=dto.formato_chaveamento,
        usuario_id=usuario.id,
    )
    return PartidaOut.model_validate(partida)


@router.post("/modalidades/{modalidade_id}/chaveamento/reset", status_code=204)
async def resetar_chaveamento(
    modalidade_id: UUID,
    dto: ResetarChaveamentoRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await chaveamento_service.resetar_chaveamento(
        db, modalidade_id, usuario_id=usuario.id, justificativa=dto.justificativa
    )
    return Response(status_code=204)
