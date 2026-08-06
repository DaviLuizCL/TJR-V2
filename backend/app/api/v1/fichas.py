from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.ficha import FichaCreate, FichaOut, FichaResumoOut
from app.schemas.simulacao import SimulacaoRequest, SimulacaoResponse
from app.services import calculo
from app.services import ficha as ficha_service
from app.services.modalidade import obter_modalidade

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/fichas", response_model=FichaOut, status_code=201)
async def criar_ficha(
    dto: FichaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> FichaOut:
    ficha = await ficha_service.criar_ficha(db, dto, usuario_id=usuario.id)
    ficha.grupos = []
    return FichaOut.model_validate(ficha)


@router.get("/fichas", response_model=Pagina[FichaResumoOut])
async def listar_fichas(
    modalidade_id: UUID | None = None,
    nivel: int | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[FichaResumoOut]:
    itens, total = await ficha_service.listar_fichas(
        db, modalidade_id=modalidade_id, nivel=nivel, page=page, size=size
    )
    return Pagina(
        itens=[FichaResumoOut.model_validate(item) for item in itens],
        total=total,
        page=page,
        size=size,
    )


@router.get("/fichas/{ficha_id}", response_model=FichaOut)
async def obter_ficha(
    ficha_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> FichaOut:
    ficha = await ficha_service.obter_ficha_completa(db, ficha_id)
    return FichaOut.model_validate(ficha)


@router.delete("/fichas/{ficha_id}", status_code=204)
async def excluir_ficha(
    ficha_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await ficha_service.excluir_ficha(db, ficha_id, usuario_id=usuario.id)
    return Response(status_code=204)


@router.post("/fichas/{ficha_id}/depreciar", response_model=FichaOut)
async def depreciar_ficha(
    ficha_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> FichaOut:
    ficha = await ficha_service.depreciar_ficha(db, ficha_id, usuario_id=usuario.id)
    ficha.grupos = []
    return FichaOut.model_validate(ficha)


@router.post("/fichas/{ficha_id}/publicar", response_model=FichaOut)
async def publicar_ficha(
    ficha_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> FichaOut:
    ficha = await ficha_service.publicar_ficha(db, ficha_id, usuario_id=usuario.id)
    ficha.grupos = []
    return FichaOut.model_validate(ficha)


@router.post("/fichas/{ficha_id}/simular", response_model=SimulacaoResponse)
async def simular(
    ficha_id: UUID,
    dto: SimulacaoRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> SimulacaoResponse:
    ficha = await ficha_service.obter_ficha_completa(db, ficha_id)
    modalidade = await obter_modalidade(db, ficha.modalidade_id)
    return calculo.calcular(ficha, modalidade, dto)
