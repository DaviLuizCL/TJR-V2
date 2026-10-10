from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.usuario import Papel
from app.schemas.common import EmailNormalizado, NomeObrigatorio


class UsuarioCreate(BaseModel):
    nome: NomeObrigatorio
    email: EmailNormalizado
    senha: str = Field(min_length=6)
    papel: Papel


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    papel: Papel
    ativo: bool


class UsuarioUpdate(BaseModel):
    nome: NomeObrigatorio | None = None
    papel: Papel | None = None
    ativo: bool | None = None


class SenhaIn(BaseModel):
    senha: str = Field(min_length=6)
