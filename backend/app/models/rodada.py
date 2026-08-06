import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class ModoHorario(StrEnum):
    MANUAL = "MANUAL"
    AUTOMATICO = "AUTOMATICO"


class RodadaStatus(StrEnum):
    AGENDADA = "AGENDADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    ENCERRADA = "ENCERRADA"


class Rodada(TimestampedBase):
    __tablename__ = "rodada"

    modalidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modalidade.id"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    modo_horario: Mapped[ModoHorario] = mapped_column(Enum(ModoHorario, name="modo_horario"))
    horario_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RodadaStatus] = mapped_column(Enum(RodadaStatus, name="rodada_status"))
