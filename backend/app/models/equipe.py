from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Equipe(TimestampedBase):
    __tablename__ = "equipe"

    nome: Mapped[str] = mapped_column(String(200))
    nivel: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Presenca no dia: equipe ausente nao entra no chaveamento montado na mao.
    presente: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
