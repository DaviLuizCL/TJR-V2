from datetime import date
from enum import StrEnum

from sqlalchemy import Date, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class EventoStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    ATIVO = "ATIVO"
    ENCERRADO = "ENCERRADO"


class Evento(TimestampedBase):
    __tablename__ = "evento"

    nome: Mapped[str] = mapped_column(String(200))
    ano: Mapped[int] = mapped_column(Integer)
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    status: Mapped[EventoStatus] = mapped_column(Enum(EventoStatus, name="evento_status"))
