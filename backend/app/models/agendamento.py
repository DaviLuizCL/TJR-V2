import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Agendamento(TimestampedBase):
    __tablename__ = "agendamento"
    __table_args__ = (
        UniqueConstraint("rodada_id", "equipe_id", name="uq_agendamento_rodada_equipe"),
        UniqueConstraint(
            "rodada_id", "arena_id", "ordem_na_arena", name="uq_agendamento_rodada_arena_ordem"
        ),
    )

    rodada_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rodada.id"), index=True
    )
    equipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), index=True
    )
    arena_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arena.id"), index=True
    )
    ordem_na_arena: Mapped[int] = mapped_column(Integer)
    horario_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
