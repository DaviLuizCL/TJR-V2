import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class TipoRegra(StrEnum):
    MANUAL = "MANUAL"
    CADERNO_ALUNO = "CADERNO_ALUNO"


class RegraModalidade(TimestampedBase):
    """PDF de regras de uma modalidade (manual completo ou caderninho do aluno).

    Fica no proprio banco, nao em disco: entra no backup do pg_dump sem passo
    extra e sobrevive a troca de servidor.
    """

    __tablename__ = "regra_modalidade"
    __table_args__ = (UniqueConstraint("modalidade_id", "tipo"),)

    modalidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modalidade.id"), index=True
    )
    tipo: Mapped[TipoRegra] = mapped_column(Enum(TipoRegra, name="tipo_regra"))
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    conteudo: Mapped[bytes] = mapped_column(LargeBinary)
    enviado_por_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id"))
