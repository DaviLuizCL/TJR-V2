import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class SolicitacaoStatus(StrEnum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    RECUSADA = "RECUSADA"


class SolicitacaoAcesso(TimestampedBase):
    """Pedido de conta feito pelo proprio juiz, sem login. Nao da acesso a
    nada ate um coordenador aprovar (ai vira Usuario ARBITRO)."""

    __tablename__ = "solicitacao_acesso"

    nome: Mapped[str] = mapped_column(String(200))
    # Sem unique: quem foi recusado pode pedir de novo.
    email: Mapped[str] = mapped_column(String(255), index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[SolicitacaoStatus] = mapped_column(
        Enum(SolicitacaoStatus, name="solicitacao_status"), default=SolicitacaoStatus.PENDENTE
    )
    decidido_por_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True
    )
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usuario_criado_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True
    )
