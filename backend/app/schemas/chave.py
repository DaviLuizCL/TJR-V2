from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import NomeObrigatorio


class ChaveCreate(BaseModel):
    modalidade_id: UUID
    nivel: int
    nome: NomeObrigatorio


class ChaveEquipeCreate(BaseModel):
    equipe_id: UUID


class ChaveOut(BaseModel):
    id: UUID
    modalidade_id: UUID
    nivel: int
    nome: str
    equipe_ids: list[UUID]


class ClassificacaoChaveItem(BaseModel):
    equipe_id: UUID
    nota_final: float
    vitorias: int
    empates: int
    derrotas: int
    posicao: int
