from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EquipeCreate(BaseModel):
    nome: str
    nivel: int = Field(ge=1, le=4)
    ativo: bool = True


class EquipeUpdate(BaseModel):
    nome: str | None = None
    nivel: int | None = Field(default=None, ge=1, le=4)
    ativo: bool | None = None


class EquipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    nivel: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
