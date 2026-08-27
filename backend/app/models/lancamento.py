import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class LancamentoStatus(StrEnum):
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    ANULADO = "ANULADO"


class Lancamento(TimestampedBase):
    __tablename__ = "lancamento"
    __table_args__ = (
        UniqueConstraint("client_operation_id", name="uq_lancamento_client_operation_id"),
    )

    ficha_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ficha.id"), index=True
    )
    rodada_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rodada.id"), index=True
    )
    tentativa: Mapped[int] = mapped_column(Integer)
    equipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), index=True
    )
    partida_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partida.id"), nullable=True
    )
    arbitro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id"))

    client_operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[LancamentoStatus] = mapped_column(
        Enum(LancamentoStatus, name="lancamento_status")
    )
    total: Mapped[float] = mapped_column(Numeric)
    # Preenchido pelo arbitro em modalidade INDIVIDUAL (tempo que a equipe
    # levou na rodada) -- usado como criterio de desempate configuravel
    # (Modalidade.desempates, regra "MENOR_TEMPO"). Opcional: nem toda
    # modalidade usa esse desempate.
    tempo_gasto_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
