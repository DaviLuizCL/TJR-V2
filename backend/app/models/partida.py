import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase
from app.models.modalidade import FormatoChaveamento


class PartidaStatus(StrEnum):
    AGENDADA = "AGENDADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    ENCERRADA = "ENCERRADA"
    EMPATADA = "EMPATADA"


class Partida(TimestampedBase):
    __tablename__ = "partida"

    rodada_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rodada.id"), index=True
    )
    equipe_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipe.id"))
    equipe_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), nullable=True
    )
    vencedor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipe.id"), nullable=True
    )
    nivel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[PartidaStatus] = mapped_column(Enum(PartidaStatus, name="partida_status"))

    # Snapshot do formato usado pro nivel dessa partida no momento em que ela
    # foi criada (mesmo principio do criterio_snapshot em LancamentoItem):
    # antes, quem decidia mata-mata vs todos-contra-todos pra QUALQUER
    # partida era o campo unico Modalidade.formato_chaveamento; agora que o
    # formato pode variar por nivel dentro da mesma modalidade (regra
    # <=5 equipes = todos-contra-todos, 6+ = mata-mata), cada partida precisa
    # guardar o proprio formato, imune a mudanca futura de contagem de
    # equipes ou de config da modalidade.
    formato_chaveamento: Mapped[FormatoChaveamento] = mapped_column(
        Enum(FormatoChaveamento, name="formato_chaveamento")
    )
