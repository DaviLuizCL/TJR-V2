from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import NomeObrigatorio


class EquipeCreate(BaseModel):
    nome: NomeObrigatorio
    nivel: int = Field(ge=1, le=4)
    ativo: bool = True


class EquipeUpdate(BaseModel):
    nome: NomeObrigatorio | None = None
    nivel: int | None = Field(default=None, ge=1, le=4)
    ativo: bool | None = None
    presente: bool | None = None


class EquipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    nivel: int
    ativo: bool
    presente: bool
    criado_em: datetime
    atualizado_em: datetime
