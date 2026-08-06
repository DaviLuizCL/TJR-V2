from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RankingModalidadeResumoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str


class ClassificacaoItemOut(BaseModel):
    equipe_id: UUID
    equipe_nome: str
    equipe_nivel: int | None
    nota_final: float
    vitorias: int
    empates: int
    derrotas: int
    eliminado_por_nome: str | None
    posicao: int


class RankingOut(BaseModel):
    modalidade_id: UUID
    modalidade_nome: str
    tipo_disputa: str
    formato_chaveamento: str | None
    ranking_liberado: bool
    itens: list[ClassificacaoItemOut]
