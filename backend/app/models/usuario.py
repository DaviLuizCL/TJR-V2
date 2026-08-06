from enum import StrEnum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Papel(StrEnum):
    COORDENADOR = "COORDENADOR"
    ARBITRO = "ARBITRO"
    SECRETARIA = "SECRETARIA"
    PUBLICO = "PUBLICO"


class Usuario(TimestampedBase):
    __tablename__ = "usuario"

    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[Papel] = mapped_column(Enum(Papel, name="papel_usuario"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
