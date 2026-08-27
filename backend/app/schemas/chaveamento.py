from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import NomeObrigatorio


class GerarChaveamentoRequest(BaseModel):
    modalidade_id: UUID


class CriarPartidaManualRequest(BaseModel):
    equipe_a_id: UUID
    equipe_b_id: UUID | None = None


class ResetarChaveamentoRequest(BaseModel):
    justificativa: NomeObrigatorio
