import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Arena(TimestampedBase):
    __tablename__ = "arena"

    modalidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modalidade.id"), index=True
    )
    nome: Mapped[str] = mapped_column(String(200))
    niveis_aplicaveis: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
