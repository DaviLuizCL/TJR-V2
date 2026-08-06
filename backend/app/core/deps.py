from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decodificar_token
from app.db.session import get_db
from app.models.usuario import Papel, Usuario

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
_oauth2_opcional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_usuario_atual(
    token: str = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    try:
        payload = decodificar_token(token)
    except ValueError as exc:
        raise AppError(
            codigo="TOKEN_INVALIDO", mensagem="Token invalido ou expirado.", status_code=401
        ) from exc

    if payload.get("tipo") != "access":
        raise AppError(codigo="TOKEN_INVALIDO", mensagem="Token nao e de acesso.", status_code=401)

    usuario = await db.get(Usuario, UUID(payload["sub"]))
    if usuario is None or not usuario.ativo:
        raise AppError(
            codigo="TOKEN_INVALIDO", mensagem="Usuario invalido ou inativo.", status_code=401
        )

    return usuario


async def obter_papel_atual(
    token: str | None = Depends(_oauth2_opcional),
    db: AsyncSession = Depends(get_db),
) -> Papel:
    """Resolve o papel de quem chama sem exigir login: sem token, ou com token
    invalido/expirado, e tratado como Papel.PUBLICO. Usado no ranking publico,
    que fica aberto no ginasio sem senha (secao 8/12 do CLAUDE.md).
    """
    if token is None:
        return Papel.PUBLICO

    try:
        payload = decodificar_token(token)
    except ValueError:
        return Papel.PUBLICO

    if payload.get("tipo") != "access":
        return Papel.PUBLICO

    usuario = await db.get(Usuario, UUID(payload["sub"]))
    if usuario is None or not usuario.ativo:
        return Papel.PUBLICO

    return usuario.papel


def exigir_papel(*papeis: Papel) -> Callable[..., Awaitable[Usuario]]:
    async def _checar(usuario: Usuario = Depends(get_usuario_atual)) -> Usuario:
        if usuario.papel not in papeis:
            raise AppError(
                codigo="PAPEL_NAO_AUTORIZADO",
                mensagem="Seu papel nao tem permissao para esta acao.",
                status_code=403,
            )
        return usuario

    return _checar
