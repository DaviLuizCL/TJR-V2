import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class TipoDisputa(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    CONFRONTO = "CONFRONTO"


class FormatoChaveamento(StrEnum):
    MATA_MATA = "MATA_MATA"
    TODOS_CONTRA_TODOS = "TODOS_CONTRA_TODOS"


class Consolidacao(StrEnum):
    SOMA_RODADAS = "SOMA_RODADAS"
    MELHOR_RODADA = "MELHOR_RODADA"
    MELHOR_N_RODADAS = "MELHOR_N_RODADAS"
    IGNORA_MENOR_NOTA = "IGNORA_MENOR_NOTA"


class ModalidadeStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    PUBLICADA = "PUBLICADA"
    ENCERRADA = "ENCERRADA"


class Modalidade(TimestampedBase):
    __tablename__ = "modalidade"

    evento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evento.id"), index=True
    )
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(String, nullable=True)

    tipo_disputa: Mapped[TipoDisputa] = mapped_column(Enum(TipoDisputa, name="tipo_disputa"))
    formato_chaveamento: Mapped[FormatoChaveamento | None] = mapped_column(
        Enum(FormatoChaveamento, name="formato_chaveamento"), nullable=True
    )

    niveis_aplicaveis: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    ficha_unica_entre_niveis: Mapped[bool] = mapped_column(Boolean)

    qtd_rodadas: Mapped[int] = mapped_column(Integer)
    tentativas_por_rodada: Mapped[int] = mapped_column(Integer, default=1)
    duracao_maxima_rodada_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pausa_entre_rodadas_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)

    consolidacao: Mapped[Consolidacao] = mapped_column(Enum(Consolidacao, name="consolidacao"))
    consolidacao_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    permite_total_negativo: Mapped[bool] = mapped_column(Boolean, default=False)

    desempates: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    pontos_vitoria: Mapped[float] = mapped_column(Numeric, default=3)
    pontos_empate: Mapped[float] = mapped_column(Numeric, default=1)

    status: Mapped[ModalidadeStatus] = mapped_column(
        Enum(ModalidadeStatus, name="modalidade_status")
    )
    ranking_liberado: Mapped[bool] = mapped_column(Boolean, default=False)
