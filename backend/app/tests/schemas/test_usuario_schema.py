import pytest
from pydantic import ValidationError

from app.models.usuario import Papel
from app.schemas.usuario import UsuarioCreate


def _payload(**overrides):
    base = dict(nome="Coordenador", email="c@tjr.app", senha="senha-123", papel=Papel.COORDENADOR)
    base.update(overrides)
    return base


def test_usuario_create_aceita_nome_valido():
    dto = UsuarioCreate(**_payload())

    assert dto.nome == "Coordenador"


def test_usuario_create_rejeita_nome_so_com_espacos():
    with pytest.raises(ValidationError):
        UsuarioCreate(**_payload(nome="   "))


def test_usuario_create_tira_espaco_das_pontas_do_nome():
    dto = UsuarioCreate(**_payload(nome="  Coordenador  "))

    assert dto.nome == "Coordenador"
