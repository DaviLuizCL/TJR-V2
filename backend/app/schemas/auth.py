from pydantic import BaseModel

from app.schemas.common import EmailNormalizado


class LoginRequest(BaseModel):
    email: EmailNormalizado
    senha: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
