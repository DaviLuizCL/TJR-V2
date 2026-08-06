from pydantic import BaseModel, EmailStr

from app.models.usuario import Papel


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    id: str
    nome: str
    email: str
    papel: Papel

    model_config = {"from_attributes": True}
