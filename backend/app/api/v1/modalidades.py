from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.modalidade import ModalidadeCreate, ModalidadeOut, ModalidadeUpdate
from app.services import modalidade as modalidade_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/modalidades", response_model=ModalidadeOut, status_code=201)
async def criar_modalidade(
    dto: ModalidadeCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> ModalidadeOut:
    modalidade = await modalidade_service.criar_modalidade(db, dto, usuario_id=usuario.id)
    return ModalidadeOut.model_validate(modalidade)


@router.get("/modalidades", response_model=Pagina[ModalidadeOut])
async def listar_modalidades(
    evento_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[ModalidadeOut]:
    itens, total = await modalidade_service.listar_modalidades(
        db, evento_id=evento_id, page=page, size=size
    )
    return Pagina(
        itens=[ModalidadeOut.model_validate(item) for item in itens],
        total=total,
        page=page,
        size=size,
    )


@router.get("/modalidades/{modalidade_id}", response_model=ModalidadeOut)
async def obter_modalidade(
    modalidade_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> ModalidadeOut:
    modalidade = await modalidade_service.obter_modalidade(db, modalidade_id)
    return ModalidadeOut.model_validate(modalidade)


@router.patch("/modalidades/{modalidade_id}", response_model=ModalidadeOut)
async def atualizar_modalidade(
    modalidade_id: UUID,
    dto: ModalidadeUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> ModalidadeOut:
    modalidade = await modalidade_service.atualizar_modalidade(
        db, modalidade_id, dto, usuario_id=usuario.id
    )
    return ModalidadeOut.model_validate(modalidade)
