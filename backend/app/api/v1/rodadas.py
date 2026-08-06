from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.partida import PartidaOut
from app.schemas.rodada import GerarRodadasRequest, RodadaCreate, RodadaOut, RodadaUpdate
from app.services import partida as partida_service
from app.services import rodada as rodada_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/rodadas", response_model=RodadaOut, status_code=201)
async def criar_rodada(
    dto: RodadaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> RodadaOut:
    rodada = await rodada_service.criar_rodada(db, dto, usuario_id=usuario.id)
    return RodadaOut.model_validate(rodada)


@router.post("/rodadas/gerar", response_model=list[RodadaOut])
async def gerar_rodadas(
    dto: GerarRodadasRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> list[RodadaOut]:
    rodadas = await rodada_service.gerar_rodadas(db, dto.modalidade_id, usuario_id=usuario.id)
    return [RodadaOut.model_validate(r) for r in rodadas]


@router.get("/rodadas", response_model=Pagina[RodadaOut])
async def listar_rodadas(
    modalidade_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[RodadaOut]:
    itens, total = await rodada_service.listar_rodadas(
        db, modalidade_id=modalidade_id, page=page, size=size
    )
    return Pagina(
        itens=[RodadaOut.model_validate(item) for item in itens], total=total, page=page, size=size
    )


@router.get("/rodadas/{rodada_id}", response_model=RodadaOut)
async def obter_rodada(
    rodada_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> RodadaOut:
    rodada = await rodada_service.obter_rodada(db, rodada_id)
    return RodadaOut.model_validate(rodada)


@router.patch("/rodadas/{rodada_id}", response_model=RodadaOut)
async def atualizar_rodada(
    rodada_id: UUID,
    dto: RodadaUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> RodadaOut:
    rodada = await rodada_service.atualizar_rodada(db, rodada_id, dto, usuario_id=usuario.id)
    return RodadaOut.model_validate(rodada)


@router.get("/rodadas/{rodada_id}/partidas", response_model=list[PartidaOut])
async def listar_partidas_da_rodada(
    rodada_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> list[PartidaOut]:
    partidas = await partida_service.listar_partidas_por_rodada(db, rodada_id)
    return [PartidaOut.model_validate(p) for p in partidas]
