from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.evento import EventoCreate, EventoOut, EventoUpdate
from app.services import evento as evento_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/eventos", response_model=EventoOut, status_code=201)
async def criar_evento(
    dto: EventoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> EventoOut:
    evento = await evento_service.criar_evento(db, dto, usuario_id=usuario.id)
    return EventoOut.model_validate(evento)


@router.get("/eventos", response_model=Pagina[EventoOut])
async def listar_eventos(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[EventoOut]:
    itens, total = await evento_service.listar_eventos(db, page=page, size=size)
    return Pagina(
        itens=[EventoOut.model_validate(item) for item in itens], total=total, page=page, size=size
    )


@router.get("/eventos/{evento_id}", response_model=EventoOut)
async def obter_evento(
    evento_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> EventoOut:
    evento = await evento_service.obter_evento(db, evento_id)
    return EventoOut.model_validate(evento)


@router.patch("/eventos/{evento_id}", response_model=EventoOut)
async def atualizar_evento(
    evento_id: UUID,
    dto: EventoUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> EventoOut:
    evento = await evento_service.atualizar_evento(db, evento_id, dto, usuario_id=usuario.id)
    return EventoOut.model_validate(evento)
