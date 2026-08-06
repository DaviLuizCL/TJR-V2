import uuid

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class LancamentoItem(TimestampedBase):
    __tablename__ = "lancamento_item"

    lancamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lancamento.id"), index=True
    )
    criterio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("criterio.id"), nullable=True
    )
    criterio_snapshot: Mapped[dict] = mapped_column(JSONB)
    ocorrencias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    pontos: Mapped[float] = mapped_column(Numeric)
    revision: Mapped[int] = mapped_column(Integer, default=1)
