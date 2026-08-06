import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class CategoriaCriterio(StrEnum):
    PONTUACAO = "PONTUACAO"
    PENALIDADE = "PENALIDADE"


class CriterioTipo(StrEnum):
    CONTADOR = "CONTADOR"
    BOOLEANO = "BOOLEANO"
    ESCALA = "ESCALA"
    MODIFICADOR = "MODIFICADOR"


class ModificadorTipo(StrEnum):
    PERCENTUAL = "PERCENTUAL"
    ZERA_TOTAL = "ZERA_TOTAL"


class Criterio(TimestampedBase):
    __tablename__ = "criterio"

    grupo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grupo.id"), index=True
    )
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(String, nullable=True)

    categoria: Mapped[CategoriaCriterio] = mapped_column(
        Enum(CategoriaCriterio, name="criterio_categoria")
    )
    tipo: Mapped[CriterioTipo] = mapped_column(Enum(CriterioTipo, name="criterio_tipo"))
    pontos: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    valores_permitidos: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    max_ocorrencias: Mapped[int | None] = mapped_column(Integer, nullable=True)

    modificador_tipo: Mapped[ModificadorTipo | None] = mapped_column(
        Enum(ModificadorTipo, name="modificador_tipo"), nullable=True
    )
    modificador_valor: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    ordem: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
