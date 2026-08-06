import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class FichaStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    PUBLICADA = "PUBLICADA"
    SUBSTITUIDA = "SUBSTITUIDA"
    DEPRECADA = "DEPRECADA"


class Ficha(TimestampedBase):
    __tablename__ = "ficha"
    __table_args__ = (
        UniqueConstraint(
            "modalidade_id", "nivel", "versao", name="uq_ficha_modalidade_nivel_versao"
        ),
    )

    modalidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modalidade.id"), index=True
    )
    nivel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    versao: Mapped[int] = mapped_column(Integer)
    status: Mapped[FichaStatus] = mapped_column(Enum(FichaStatus, name="ficha_status"))
    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
