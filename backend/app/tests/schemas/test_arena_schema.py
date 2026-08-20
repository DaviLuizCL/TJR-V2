import pytest
from pydantic import ValidationError

from app.schemas.arena import ArenaCreate


def _payload(**overrides):
    base = dict(modalidade_id="11111111-1111-1111-1111-111111111111", nome="Arena 1")
    base.update(overrides)
    return base


def test_arena_create_aceita_nome_valido():
    dto = ArenaCreate(**_payload())

    assert dto.nome == "Arena 1"


def test_arena_create_rejeita_nome_so_com_espacos():
    with pytest.raises(ValidationError):
        ArenaCreate(**_payload(nome="   "))


def test_arena_create_tira_espaco_das_pontas_do_nome():
    dto = ArenaCreate(**_payload(nome="  Arena 1  "))

    assert dto.nome == "Arena 1"
