from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EquipePublicaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nome: str
    posicao: int
    presente: bool
    rodadas_competidas: list[int]
    proxima: bool
    equipes_na_frente: int | None


class NivelPublicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nivel: int
    equipes: list[EquipePublicaOut]


class ModalidadePublicaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    rodadas: list[int]
    niveis: list[NivelPublicoOut]
