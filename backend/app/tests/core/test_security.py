import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
    hash_senha,
    verificar_senha,
)


def test_hash_senha_gera_hash_verificavel():
    hash_ = hash_senha("minha-senha-123")

    assert hash_ != "minha-senha-123"
    assert verificar_senha("minha-senha-123", hash_) is True


def test_verificar_senha_rejeita_senha_errada():
    hash_ = hash_senha("minha-senha-123")

    assert verificar_senha("senha-errada", hash_) is False


def test_criar_access_token_contem_sub_e_papel():
    token = criar_access_token(sub="user-id-123", papel="COORDENADOR")

    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert payload["sub"] == "user-id-123"
    assert payload["papel"] == "COORDENADOR"
    assert payload["tipo"] == "access"


def test_criar_refresh_token_tem_tipo_refresh():
    token = criar_refresh_token(sub="user-id-123")

    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert payload["sub"] == "user-id-123"
    assert payload["tipo"] == "refresh"


def test_decodificar_token_invalido_lanca_erro():
    with pytest.raises(ValueError):
        decodificar_token("token-invalido")
