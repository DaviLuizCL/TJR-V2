import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class AuditLog(TimestampedBase):
    __tablename__ = "audit_log"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id"), index=True
    )
    entidade: Mapped[str] = mapped_column(String(100))
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    acao: Mapped[str] = mapped_column(String(50))
    justificativa: Mapped[str | None] = mapped_column(String, nullable=True)
    antes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    depois: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
