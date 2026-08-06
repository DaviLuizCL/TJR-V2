from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.modalidade import Consolidacao, FormatoChaveamento, ModalidadeStatus, TipoDisputa


class ModalidadeCreate(BaseModel):
    evento_id: UUID
    nome: str
    descricao: str | None = None
    tipo_disputa: TipoDisputa
    formato_chaveamento: FormatoChaveamento | None = None
    niveis_aplicaveis: list[int]
    ficha_unica_entre_niveis: bool
    qtd_rodadas: int = Field(ge=1)
    tentativas_por_rodada: int = Field(default=1, ge=1)
    duracao_maxima_rodada_seg: int | None = Field(default=None, ge=1)
    pausa_entre_rodadas_seg: int | None = Field(default=None, ge=0)
    consolidacao: Consolidacao
    consolidacao_n: int | None = Field(default=None, ge=1)
    permite_total_negativo: bool = False
    desempates: list[dict] | None = None
    pontos_vitoria: float = 3
    pontos_empate: float = 1


class ModalidadeUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    tipo_disputa: TipoDisputa | None = None
    formato_chaveamento: FormatoChaveamento | None = None
    niveis_aplicaveis: list[int] | None = None
    ficha_unica_entre_niveis: bool | None = None
    qtd_rodadas: int | None = Field(default=None, ge=1)
    tentativas_por_rodada: int | None = Field(default=None, ge=1)
    duracao_maxima_rodada_seg: int | None = Field(default=None, ge=1)
    pausa_entre_rodadas_seg: int | None = Field(default=None, ge=0)
    consolidacao: Consolidacao | None = None
    consolidacao_n: int | None = Field(default=None, ge=1)
    permite_total_negativo: bool | None = None
    desempates: list[dict] | None = None
    status: ModalidadeStatus | None = None
    ranking_liberado: bool | None = None
    pontos_vitoria: float | None = None
    pontos_empate: float | None = None


class ModalidadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evento_id: UUID
    nome: str
    descricao: str | None
    tipo_disputa: TipoDisputa
    formato_chaveamento: FormatoChaveamento | None
    niveis_aplicaveis: list[int]
    ficha_unica_entre_niveis: bool
    qtd_rodadas: int
    tentativas_por_rodada: int
    duracao_maxima_rodada_seg: int | None
    pausa_entre_rodadas_seg: int | None
    consolidacao: Consolidacao
    consolidacao_n: int | None
    permite_total_negativo: bool
    desempates: list[dict] | None
    pontos_vitoria: float
    pontos_empate: float
    status: ModalidadeStatus
    ranking_liberado: bool
    criado_em: datetime
    atualizado_em: datetime
