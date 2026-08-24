from app.core.security import hash_senha
from app.models.usuario import Papel, Usuario


async def _criar_usuario(
    db_session, *, email="coord@tjr.app", senha="senha-123", papel=Papel.COORDENADOR, ativo=True
):
    usuario = Usuario(
        nome="Coordenador Teste",
        email=email,
        senha_hash=hash_senha(senha),
        papel=papel,
        ativo=ativo,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def test_login_com_credenciais_validas_retorna_tokens(client, db_session):
    await _criar_usuario(db_session, email="coord@tjr.app", senha="senha-123")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "coord@tjr.app", "senha": "senha-123"}
    )

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["refresh_token"]


async def test_login_com_senha_errada_retorna_401_com_erro_padronizado(client, db_session):
    await _criar_usuario(db_session, email="coord2@tjr.app", senha="senha-correta")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "coord2@tjr.app", "senha": "senha-errada"}
    )

    assert response.status_code == 401
    assert response.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_login_ignora_diferenca_de_maiusculas_minusculas_no_email(client, db_session):
    await _criar_usuario(db_session, email="case@tjr.app", senha="senha-123")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "CasE@Tjr.App", "senha": "senha-123"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_com_email_inexistente_retorna_401(client, db_session):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "ninguem@tjr.app", "senha": "qualquer"}
    )

    assert response.status_code == 401
    assert response.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_login_com_usuario_inativo_retorna_401(client, db_session):
    await _criar_usuario(db_session, email="inativo@tjr.app", senha="senha-123", ativo=False)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "inativo@tjr.app", "senha": "senha-123"}
    )

    assert response.status_code == 401
    assert response.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_refresh_com_token_valido_retorna_novos_tokens(client, db_session):
    await _criar_usuario(db_session, email="coord3@tjr.app", senha="senha-123")

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "coord3@tjr.app", "senha": "senha-123"}
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["access_token"]
    assert corpo["refresh_token"]


async def test_refresh_com_access_token_no_lugar_de_refresh_retorna_401(client, db_session):
    await _criar_usuario(db_session, email="coord4@tjr.app", senha="senha-123")

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "coord4@tjr.app", "senha": "senha-123"}
    )
    access_token = login_response.json()["access_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401
    assert response.json()["erro"]["codigo"] == "TOKEN_INVALIDO"


async def test_endpoint_protegido_sem_token_retorna_401(client):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_endpoint_protegido_com_token_valido_retorna_usuario(client, db_session):
    await _criar_usuario(db_session, email="coord5@tjr.app", senha="senha-123")

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "coord5@tjr.app", "senha": "senha-123"}
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "coord5@tjr.app"
    assert response.json()["papel"] == "COORDENADOR"
