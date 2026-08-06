from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.evento import EventoStatus


class EventoCreate(BaseModel):
    nome: str
    ano: int
    data_inicio: date
    data_fim: date


class EventoUpdate(BaseModel):
    nome: str | None = None
    ano: int | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    status: EventoStatus | None = None


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    ano: int
    data_inicio: date
    data_fim: date
    status: EventoStatus
    criado_em: datetime
    atualizado_em: datetime
