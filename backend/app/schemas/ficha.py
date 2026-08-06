from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ficha import FichaStatus
from app.schemas.grupo import GrupoOut


class FichaCreate(BaseModel):
    modalidade_id: UUID
    nivel: int | None = None


class FichaResumoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    modalidade_id: UUID
    nivel: int | None
    versao: int
    status: FichaStatus
    publicada_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime


class FichaOut(FichaResumoOut):
    grupos: list[GrupoOut] = Field(default_factory=list)
