import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Inscricao(TimestampedBase):
    __tablename__ = "inscricao"
    __table_args__ = (
        UniqueConstraint("equipe_id", "modalidade_id", name="uq_inscricao_equipe_modalidade"),
    )

    equipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), index=True
    )
    modalidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modalidade.id"), index=True
    )
