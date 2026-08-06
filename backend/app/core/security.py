from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return _pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return _pwd_context.verify(senha, senha_hash)


def _criar_token(sub: str, tipo: str, expira_em_minutos: int, extra: dict | None = None) -> str:
    agora = datetime.now(UTC)
    payload = {
        "sub": sub,
        "tipo": tipo,
        "iat": agora,
        "exp": agora + timedelta(minutes=expira_em_minutos),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def criar_access_token(sub: str, papel: str) -> str:
    return _criar_token(
        sub=sub,
        tipo="access",
        expira_em_minutos=settings.access_token_expire_minutes,
        extra={"papel": papel},
    )


def criar_refresh_token(sub: str) -> str:
    return _criar_token(
        sub=sub,
        tipo="refresh",
        expira_em_minutos=settings.refresh_token_expire_minutes,
    )


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("token invalido ou expirado") from exc
