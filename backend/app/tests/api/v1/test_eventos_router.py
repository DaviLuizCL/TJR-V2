from app.core.security import hash_senha
from app.models.usuario import Papel, Usuario


async def _criar_usuario(db_session, *, email, papel, senha="senha-123"):
    usuario = Usuario(nome="Usuario Teste", email=email, senha_hash=hash_senha(senha), papel=papel)
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


async def test_criar_evento_sem_token_retorna_401(client):
    resposta = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-03-10",
            "data_fim": "2026-03-12",
        },
    )

    assert resposta.status_code == 401


async def test_criar_evento_com_papel_arbitro_retorna_403(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-eventos@tjr.app")

    resposta = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-03-10",
            "data_fim": "2026-03-12",
        },
        headers=headers,
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_criar_evento_com_coordenador_retorna_201(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-eventos-1@tjr.app")

    resposta = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-03-10",
            "data_fim": "2026-03-12",
        },
        headers=headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "TJR 2026"
    assert corpo["status"] == "RASCUNHO"


async def test_criar_evento_quando_ja_existe_um_retorna_422(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-eventos-unico@tjr.app"
    )
    await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-03-10",
            "data_fim": "2026-03-12",
        },
        headers=headers,
    )

    resposta = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2027",
            "ano": 2027,
            "data_inicio": "2027-03-10",
            "data_fim": "2027-03-12",
        },
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "EVENTO_UNICO_JA_EXISTE"


async def test_criar_evento_com_data_fim_antes_de_inicio_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-eventos-2@tjr.app")

    resposta = await client.post(
        "/api/v1/eventos",
        json={"nome": "X", "ano": 2026, "data_inicio": "2026-03-12", "data_fim": "2026-03-10"},
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DATA_FIM_ANTES_DE_INICIO"


async def test_listar_eventos_retorna_envelope_paginado(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-eventos-3@tjr.app")
    await client.post(
        "/api/v1/eventos",
        json={
            "nome": "Evento X",
            "ano": 2026,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-01-02",
        },
        headers=headers,
    )

    resposta = await client.get("/api/v1/eventos?page=1&size=50", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["page"] == 1
    assert corpo["size"] == 50
    assert corpo["total"] >= 1
    assert isinstance(corpo["itens"], list)


async def test_arbitro_pode_listar_eventos_mas_nao_criar(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-eventos-arb-list@tjr.app"
    )
    await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-01-02",
        },
        headers=coord_headers,
    )
    arb_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-eventos-list@tjr.app"
    )

    resposta = await client.get("/api/v1/eventos", headers=arb_headers)

    assert resposta.status_code == 200
    assert resposta.json()["total"] >= 1


async def test_arbitro_pode_obter_evento_por_id(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-eventos-arb-obter@tjr.app"
    )
    criado = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-01-02",
        },
        headers=coord_headers,
    )
    evento_id = criado.json()["id"]
    arb_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-eventos-obter@tjr.app"
    )

    resposta = await client.get(f"/api/v1/eventos/{evento_id}", headers=arb_headers)

    assert resposta.status_code == 200
    assert resposta.json()["id"] == evento_id


async def test_secretaria_pode_listar_eventos(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.SECRETARIA, "secretaria-eventos-list@tjr.app"
    )

    resposta = await client.get("/api/v1/eventos", headers=headers)

    assert resposta.status_code == 200


async def test_arbitro_nao_pode_atualizar_evento(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-eventos-arb-patch@tjr.app"
    )
    criado = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-01-02",
        },
        headers=coord_headers,
    )
    evento_id = criado.json()["id"]
    arb_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-eventos-patch@tjr.app"
    )

    resposta = await client.patch(
        f"/api/v1/eventos/{evento_id}", json={"nome": "Outro nome"}, headers=arb_headers
    )

    assert resposta.status_code == 403


async def test_obter_evento_inexistente_retorna_404(client, db_session):
    import uuid

    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-eventos-4@tjr.app")

    resposta = await client.get(f"/api/v1/eventos/{uuid.uuid4()}", headers=headers)

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "EVENTO_NAO_ENCONTRADO"


async def test_atualizar_evento_altera_nome(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-eventos-5@tjr.app")
    criado = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "Nome Original",
            "ano": 2026,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-01-02",
        },
        headers=headers,
    )
    evento_id = criado.json()["id"]

    resposta = await client.patch(
        f"/api/v1/eventos/{evento_id}", json={"nome": "Nome Corrigido"}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Nome Corrigido"
