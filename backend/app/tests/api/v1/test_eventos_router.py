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
    for i in range(2):
        await client.post(
            "/api/v1/eventos",
            json={
                "nome": f"Evento {i}",
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
    assert corpo["total"] >= 2
    assert isinstance(corpo["itens"], list)


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
