import uuid

from app.schemas.criterio import CriterioCreate
from app.schemas.ficha import FichaCreate
from app.schemas.grupo import GrupoCreate


def test_ficha_create_nivel_e_opcional():
    dto = FichaCreate(modalidade_id=uuid.uuid4())

    assert dto.nivel is None


def test_grupo_create_exige_nome_e_ordem():
    dto = GrupoCreate(nome="Parte Tecnica", ordem=1)

    assert dto.nome == "Parte Tecnica"
    assert dto.ordem == 1


def test_criterio_create_aplica_default_ativo_true():
    dto = CriterioCreate(nome="Lombada", categoria="PONTUACAO", tipo="CONTADOR", pontos=10, ordem=1)

    assert dto.ativo is True
