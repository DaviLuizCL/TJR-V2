from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_usuario_atual
from app.core.errors import AppError
from app.core.security import (
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
    verificar_senha,
)
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.usuario import UsuarioOut

router = APIRouter()


def _tokens_para(usuario: Usuario) -> TokenResponse:
    return TokenResponse(
        access_token=criar_access_token(sub=str(usuario.id), papel=usuario.papel.value),
        refresh_token=criar_refresh_token(sub=str(usuario.id)),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(dados: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    resultado = await db.execute(select(Usuario).where(Usuario.email == dados.email))
    usuario = resultado.scalar_one_or_none()

    credenciais_invalidas = AppError(
        codigo="CREDENCIAIS_INVALIDAS",
        mensagem="Email ou senha invalidos.",
        status_code=401,
    )

    if usuario is None or not usuario.ativo:
        raise credenciais_invalidas
    if not verificar_senha(dados.senha, usuario.senha_hash):
        raise credenciais_invalidas

    return _tokens_para(usuario)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(dados: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        payload = decodificar_token(dados.refresh_token)
    except ValueError as exc:
        raise AppError(
            codigo="TOKEN_INVALIDO", mensagem="Refresh token invalido ou expirado.", status_code=401
        ) from exc

    if payload.get("tipo") != "refresh":
        raise AppError(
            codigo="TOKEN_INVALIDO",
            mensagem="Token informado nao e um refresh token.",
            status_code=401,
        )

    usuario = await db.get(Usuario, UUID(payload["sub"]))
    if usuario is None or not usuario.ativo:
        raise AppError(
            codigo="TOKEN_INVALIDO", mensagem="Usuario invalido ou inativo.", status_code=401
        )

    return _tokens_para(usuario)


@router.get("/auth/me", response_model=UsuarioOut)
async def me(usuario: Usuario = Depends(get_usuario_atual)) -> UsuarioOut:
    return UsuarioOut.model_validate(usuario)
