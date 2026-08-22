from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GerarAgendamentosRequest(BaseModel):
    modalidade_id: UUID
    rodada_ids: list[UUID] = Field(min_length=1)
    horario_inicio: datetime
    regenerar: bool = False


class AgendamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rodada_id: UUID
    equipe_id: UUID
    arena_id: UUID
    ordem_na_arena: int
    horario_inicio: datetime
    criado_em: datetime
    atualizado_em: datetime


class AgendamentoEstimativaOut(BaseModel):
    agendamento_id: UUID
    horario_previsto: datetime
