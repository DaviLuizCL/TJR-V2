import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Grupo(TimestampedBase):
    __tablename__ = "grupo"

    ficha_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ficha.id"), index=True
    )
    nome: Mapped[str] = mapped_column(String(200))
    ordem: Mapped[int] = mapped_column(Integer)
