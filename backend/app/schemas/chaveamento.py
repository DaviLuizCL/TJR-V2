from uuid import UUID

from pydantic import BaseModel


class GerarChaveamentoRequest(BaseModel):
    modalidade_id: UUID
