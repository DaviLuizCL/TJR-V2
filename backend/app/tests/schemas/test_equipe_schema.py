import pytest
from pydantic import ValidationError

from app.schemas.equipe import EquipeCreate, EquipeUpdate


def test_equipe_create_aceita_nome_valido():
    dto = EquipeCreate(nome="Equipe Alpha", nivel=2)

    assert dto.nome == "Equipe Alpha"


def test_equipe_create_rejeita_nome_so_com_espacos():
    with pytest.raises(ValidationError):
        EquipeCreate(nome="   ", nivel=2)


def test_equipe_create_rejeita_nome_vazio():
    with pytest.raises(ValidationError):
        EquipeCreate(nome="", nivel=2)


def test_equipe_create_tira_espaco_das_pontas_do_nome():
    dto = EquipeCreate(nome="  Equipe Alpha  ", nivel=2)

    assert dto.nome == "Equipe Alpha"


def test_equipe_update_rejeita_nome_so_com_espacos_quando_informado():
    with pytest.raises(ValidationError):
        EquipeUpdate(nome="   ")


def test_equipe_update_permite_omitir_nome():
    dto = EquipeUpdate(nivel=3)

    assert dto.nome is None
