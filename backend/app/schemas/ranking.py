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
    # Formato do NIVEL dessa equipe (nao mais um campo unico da modalidade
    # inteira -- niveis diferentes podem estar em formatos diferentes, ver
    # consolidacao.py::_formato_por_nivel). None so em modalidade INDIVIDUAL.
    formato_chaveamento: str | None


class RankingOut(BaseModel):
    modalidade_id: UUID
    modalidade_nome: str
    tipo_disputa: str
    formato_chaveamento: str | None
    ranking_liberado: bool
    itens: list[ClassificacaoItemOut]
