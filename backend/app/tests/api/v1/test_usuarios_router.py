from app.core.security import hash_senha
from app.models.usuario import Papel, Usuario


async def _criar_usuario(db_session, *, email, papel, senha="senha-123", ativo=True):
    usuario = Usuario(
        nome="Usuario Teste", email=email, senha_hash=hash_senha(senha), papel=papel, ativo=ativo
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _token(client, email, senha="senha-123"):
    resposta = await client.post("/api/v1/auth/login", json={"email": email, "senha": senha})
    return resposta.json()["access_token"]


async def _auth_header(client, db_session, papel, email):
    await _criar_usuario(db_session, email=email, papel=papel)
    token = await _token(client, email)
    return {"Authorization": f"Bearer {token}"}


async def test_coordenador_cria_usuario_arbitro(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-usr-1@tjr.app")

    resposta = await client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Arbitro Novo",
            "email": "arbitro-criado@tjr.app",
            "senha": "senha-forte",
            "papel": "ARBITRO",
        },
        headers=headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["email"] == "arbitro-criado@tjr.app"
    assert corpo["papel"] == "ARBITRO"
    assert corpo["ativo"] is True
    assert "senha" not in corpo
    assert "senha_hash" not in corpo


async def test_arbitro_nao_pode_criar_usuario(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arb-usr-1@tjr.app")

    resposta = await client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Outro",
            "email": "outro@tjr.app",
            "senha": "senha-forte",
            "papel": "ARBITRO",
        },
        headers=headers,
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_criar_usuario_sem_token_retorna_401(client):
    resposta = await client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Outro",
            "email": "sem-token@tjr.app",
            "senha": "senha-forte",
            "papel": "ARBITRO",
        },
    )

    assert resposta.status_code == 401


async def test_criar_usuario_com_email_duplicado_retorna_409(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-usr-2@tjr.app")
    payload = {
        "nome": "Duplicado",
        "email": "duplicado-router@tjr.app",
        "senha": "senha-forte",
        "papel": "SECRETARIA",
    }
    primeira = await client.post("/api/v1/usuarios", json=payload, headers=headers)
    assert primeira.status_code == 201

    segunda = await client.post("/api/v1/usuarios", json=payload, headers=headers)

    assert segunda.status_code == 409
    assert segunda.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"


async def test_criar_usuario_com_senha_curta_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-usr-3@tjr.app")

    resposta = await client.post(
        "/api/v1/usuarios",
        json={"nome": "Curto", "email": "senha-curta@tjr.app", "senha": "123", "papel": "ARBITRO"},
        headers=headers,
    )

    assert resposta.status_code == 422


async def test_coordenador_lista_usuarios(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-usr-4@tjr.app")
    await client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Arbitro Listado",
            "email": "arbitro-listado@tjr.app",
            "senha": "senha-forte",
            "papel": "ARBITRO",
        },
        headers=headers,
    )

    resposta = await client.get("/api/v1/usuarios", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    nomes = [item["nome"] for item in corpo["itens"]]
    assert "Arbitro Listado" in nomes
    assert corpo["total"] >= 2  # coordenador logado + arbitro criado


async def test_secretaria_nao_pode_listar_usuarios(client, db_session):
    headers = await _auth_header(client, db_session, Papel.SECRETARIA, "sec-usr-1@tjr.app")

    resposta = await client.get("/api/v1/usuarios", headers=headers)

    assert resposta.status_code == 403


async def _criar_juiz(client, headers, email):
    resposta = await client.post(
        "/api/v1/usuarios",
        json={"nome": "Juiz", "email": email, "senha": "senha-antiga", "papel": "ARBITRO"},
        headers=headers,
    )
    return resposta.json()["id"]


async def test_patch_usuario_desativa_e_juiz_nao_consegue_mais_logar(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-edit-1@tjr.app")
    juiz_id = await _criar_juiz(client, headers, "juiz-edit-1@tjr.app")

    resposta = await client.patch(
        f"/api/v1/usuarios/{juiz_id}", json={"ativo": False}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["ativo"] is False
    login = await client.post(
        "/api/v1/auth/login", json={"email": "juiz-edit-1@tjr.app", "senha": "senha-antiga"}
    )
    assert login.status_code == 401


async def test_trocar_senha_permite_logar_com_a_senha_nova(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-edit-2@tjr.app")
    juiz_id = await _criar_juiz(client, headers, "juiz-edit-2@tjr.app")

    resposta = await client.post(
        f"/api/v1/usuarios/{juiz_id}/senha", json={"senha": "senha-nova"}, headers=headers
    )

    assert resposta.status_code == 204
    login = await client.post(
        "/api/v1/auth/login", json={"email": "juiz-edit-2@tjr.app", "senha": "senha-nova"}
    )
    assert login.status_code == 200


async def test_trocar_senha_curta_demais_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-edit-3@tjr.app")
    juiz_id = await _criar_juiz(client, headers, "juiz-edit-3@tjr.app")

    resposta = await client.post(
        f"/api/v1/usuarios/{juiz_id}/senha", json={"senha": "123"}, headers=headers
    )

    assert resposta.status_code == 422


async def test_arbitro_nao_pode_editar_usuario(client, db_session):
    coord = await _auth_header(client, db_session, Papel.COORDENADOR, "c-edit-4@tjr.app")
    juiz_id = await _criar_juiz(client, coord, "juiz-edit-4@tjr.app")
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "a-edit-4@tjr.app")

    patch = await client.patch(
        f"/api/v1/usuarios/{juiz_id}", json={"ativo": False}, headers=headers
    )
    senha = await client.post(
        f"/api/v1/usuarios/{juiz_id}/senha", json={"senha": "senha-nova"}, headers=headers
    )

    assert patch.status_code == 403
    assert senha.status_code == 403
