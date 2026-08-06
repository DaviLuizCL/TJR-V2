from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.criterio import CategoriaCriterio, CriterioTipo, ModificadorTipo


class CriterioCreate(BaseModel):
    nome: str
    descricao: str | None = None
    categoria: CategoriaCriterio
    tipo: CriterioTipo
    pontos: float | None = None
    valores_permitidos: list | None = None
    max_ocorrencias: int | None = None
    modificador_tipo: ModificadorTipo | None = None
    modificador_valor: float | None = None
    ordem: int
    ativo: bool = True


class CriterioUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    categoria: CategoriaCriterio | None = None
    tipo: CriterioTipo | None = None
    pontos: float | None = None
    valores_permitidos: list | None = None
    max_ocorrencias: int | None = None
    modificador_tipo: ModificadorTipo | None = None
    modificador_valor: float | None = None
    ordem: int | None = None
    ativo: bool | None = None


class CriterioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grupo_id: UUID
    nome: str
    descricao: str | None
    categoria: CategoriaCriterio
    tipo: CriterioTipo
    pontos: float | None
    valores_permitidos: list | None
    max_ocorrencias: int | None
    modificador_tipo: ModificadorTipo | None
    modificador_valor: float | None
    ordem: int
    ativo: bool
