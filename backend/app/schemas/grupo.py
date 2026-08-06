from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.criterio import CriterioOut


class GrupoCreate(BaseModel):
    nome: str
    ordem: int


class GrupoUpdate(BaseModel):
    nome: str | None = None
    ordem: int | None = None


class GrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ficha_id: UUID
    nome: str
    ordem: int
    criterios: list[CriterioOut] = Field(default_factory=list)
