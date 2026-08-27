from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.lancamento import LancamentoStatus


class ItemLancamentoInput(BaseModel):
    criterio_id: UUID
    ocorrencias: int | None = Field(default=None, ge=0)
    valor: float | None = None
    aplicado: bool | None = None


class LancamentoCreate(BaseModel):
    ficha_id: UUID
    rodada_id: UUID
    tentativa: int = 1
    equipe_id: UUID
    partida_id: UUID | None = None
    client_operation_id: UUID
    itens: list[ItemLancamentoInput]
    tempo_gasto_seg: int | None = Field(default=None, ge=0)


class LancamentoCorrigir(BaseModel):
    # Opcional de proposito (pedido explicito do cliente, 2026-08-25) -- o
    # audit_log continua registrando o que for preenchido, mas nao bloqueia
    # mais a correcao quando vem em branco.
    justificativa: str = ""
    revision: int
    itens: list[ItemLancamentoInput]


class ItemLancamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    criterio_id: UUID | None
    criterio_snapshot: dict
    ocorrencias: int | None
    valor: float | None
    pontos: float


class LancamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ficha_id: UUID
    rodada_id: UUID
    tentativa: int
    equipe_id: UUID
    partida_id: UUID | None
    arbitro_id: UUID
    client_operation_id: UUID
    revision: int
    status: LancamentoStatus
    total: float
    tempo_gasto_seg: int | None
    itens: list[ItemLancamentoOut]
    criado_em: datetime
    atualizado_em: datetime


class LancamentoAuditoriaOut(BaseModel):
    id: UUID
    modalidade_nome: str
    nivel: int | None
    equipe_nome: str
    rodada_numero: int
    tentativa: int
    partida_id: UUID | None
    responsavel_nome: str
    horario_submissao: datetime
    status: LancamentoStatus
    total: float
    itens: list[ItemLancamentoOut]
