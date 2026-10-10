from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.usuario import SenhaIn, UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services import usuario as usuario_service

router = APIRouter()


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
async def criar_usuario(
    dto: UsuarioCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> UsuarioOut:
    novo = await usuario_service.criar_usuario(db, dto, usuario_id=usuario.id)
    return UsuarioOut.model_validate(novo)


@router.get("/usuarios", response_model=Pagina[UsuarioOut])
async def listar_usuarios(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Pagina[UsuarioOut]:
    itens, total = await usuario_service.listar_usuarios(db, page=page, size=size)
    return Pagina(
        itens=[UsuarioOut.model_validate(item) for item in itens], total=total, page=page, size=size
    )


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
async def atualizar_usuario(
    usuario_id: UUID,
    dto: UsuarioUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> UsuarioOut:
    atualizado = await usuario_service.atualizar_usuario(db, usuario_id, dto, usuario_id=usuario.id)
    return UsuarioOut.model_validate(atualizado)


@router.post("/usuarios/{usuario_id}/senha", status_code=204)
async def definir_senha(
    usuario_id: UUID,
    dto: SenhaIn,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await usuario_service.definir_senha(db, usuario_id, dto.senha, usuario_id=usuario.id)
    return Response(status_code=204)
