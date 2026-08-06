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
    criado_em: datetime
    atualizado_em: datetime
