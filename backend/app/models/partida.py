import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class PartidaStatus(StrEnum):
    AGENDADA = "AGENDADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    ENCERRADA = "ENCERRADA"
    EMPATADA = "EMPATADA"


class Partida(TimestampedBase):
    __tablename__ = "partida"

    rodada_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rodada.id"), index=True
    )
    equipe_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipe.id"))
    equipe_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), nullable=True
    )
    vencedor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), nullable=True
    )
    nivel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[PartidaStatus] = mapped_column(Enum(PartidaStatus, name="partida_status"))
