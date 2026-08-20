from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.usuario import Papel
from app.schemas.common import NomeObrigatorio


class UsuarioCreate(BaseModel):
    nome: NomeObrigatorio
    email: EmailStr
    senha: str = Field(min_length=6)
    papel: Papel


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    papel: Papel
    ativo: bool
