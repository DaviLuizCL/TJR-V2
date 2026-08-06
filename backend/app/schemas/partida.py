from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.partida import PartidaStatus


class PartidaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rodada_id: UUID
    equipe_a_id: UUID
    equipe_b_id: UUID | None
    vencedor_id: UUID | None
    nivel: int | None
    status: PartidaStatus
    criado_em: datetime
    atualizado_em: datetime
