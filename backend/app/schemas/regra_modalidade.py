from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.regra_modalidade import TipoRegra


class RegraResumoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tipo: TipoRegra
    nome_arquivo: str
    atualizado_em: datetime


class ModalidadeComRegrasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    regras: list[RegraResumoOut]
