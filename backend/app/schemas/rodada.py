from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.rodada import ModoHorario, RodadaStatus


class RodadaCreate(BaseModel):
    modalidade_id: UUID
    numero: int = Field(ge=1)
    modo_horario: ModoHorario
    horario_inicio: datetime | None = None


class GerarRodadasRequest(BaseModel):
    modalidade_id: UUID


class RodadaUpdate(BaseModel):
    modo_horario: ModoHorario | None = None
    horario_inicio: datetime | None = None
    status: RodadaStatus | None = None


class RodadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    modalidade_id: UUID
    numero: int
    modo_horario: ModoHorario
    horario_inicio: datetime | None
    status: RodadaStatus
    criado_em: datetime
    atualizado_em: datetime
