import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Chave(TimestampedBase):
    """Sub-grupo de equipes de um nivel, dentro de uma modalidade CONFRONTO,
    usado na fase de grupos (cada chave joga todos-contra-todos entre si).
    Diferente de `Grupo` (secao de ficha de pontuao) -- conceitos de dominio
    distintos, mesmo soando parecido em portugues.
    """

    __tablename__ = "chave"

    modalidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modalidade.id"), index=True
    )
    nivel: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(200))


class ChaveEquipe(TimestampedBase):
    __tablename__ = "chave_equipe"
    __table_args__ = (
        UniqueConstraint("chave_id", "equipe_id", name="uq_chave_equipe_chave_equipe"),
    )

    chave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chave.id"), index=True
    )
    equipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), index=True
    )
