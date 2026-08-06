from uuid import UUID

from pydantic import BaseModel


class ValorCriterioSimulado(BaseModel):
    criterio_id: UUID
    ocorrencias: int | None = None
    valor: float | None = None
    aplicado: bool | None = None


class SimulacaoRequest(BaseModel):
    valores: list[ValorCriterioSimulado]


class DetalheCriterio(BaseModel):
    criterio_id: UUID
    nome: str
    tipo: str
    entrada: dict
    pontos: float


class ModificadorAplicado(BaseModel):
    criterio_id: UUID
    nome: str
    tipo: str
    valor: float | None


class SimulacaoResponse(BaseModel):
    total: float
    subtotais_por_grupo: dict[str, float]
    detalhamento_por_criterio: list[DetalheCriterio]
    modificadores_aplicados: list[ModificadorAplicado]
