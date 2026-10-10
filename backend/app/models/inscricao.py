import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
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
    # Ordem em que a equipe se apresenta (1 = primeira) dentro do seu nivel, em
    # modalidade INDIVIDUAL. Mesma ordem pra todas as rodadas; None = ainda nao
    # sorteada. Substitui o agendamento por arena/horario.
    ordem_apresentacao: Mapped[int | None] = mapped_column(Integer, nullable=True)
