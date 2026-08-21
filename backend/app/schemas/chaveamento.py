from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import NomeObrigatorio


class GerarChaveamentoRequest(BaseModel):
    modalidade_id: UUID


class ResetarChaveamentoRequest(BaseModel):
    justificativa: NomeObrigatorio
