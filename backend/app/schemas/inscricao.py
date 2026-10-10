from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InscricaoCreate(BaseModel):
    equipe_id: UUID
    modalidade_id: UUID


class InscricaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    equipe_id: UUID
    modalidade_id: UUID
    ordem_apresentacao: int | None = None
    criado_em: datetime
    atualizado_em: datetime


class SortearOrdemIn(BaseModel):
    nivel: int


class DefinirOrdemIn(BaseModel):
    nivel: int
    equipe_ids: list[UUID]
