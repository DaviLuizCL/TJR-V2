from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.solicitacao_acesso import SolicitacaoStatus
from app.schemas.common import EmailNormalizado, NomeObrigatorio


class SolicitacaoAcessoCreate(BaseModel):
    nome: NomeObrigatorio
    email: EmailNormalizado
    senha: str = Field(min_length=6)


class SolicitacaoAcessoOut(BaseModel):
    """Sem senha_hash: o coordenador so precisa ver quem esta pedindo."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    status: SolicitacaoStatus
    criado_em: datetime


class AprovarSolicitacaoIn(BaseModel):
    # Pedido vem de juiz, mas o coordenador pode liberar como coordenador.
    papel: Literal["ARBITRO", "COORDENADOR"] = "ARBITRO"
