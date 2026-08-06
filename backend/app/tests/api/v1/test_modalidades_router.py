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


async def _criar_evento(client, headers, nome="TJR 2026"):
    resposta = await client.post(
        "/api/v1/eventos",
        json={"nome": nome, "ano": 2026, "data_inicio": "2026-03-10", "data_fim": "2026-03-12"},
        headers=headers,
    )
    return resposta.json()["id"]


def _payload(evento_id, **overrides):
    base = {
        "evento_id": evento_id,
        "nome": "Sumo de Robos",
        "tipo_disputa": "CONFRONTO",
        "niveis_aplicaveis": [1, 2],
        "ficha_unica_entre_niveis": False,
        "qtd_rodadas": 3,
        "consolidacao": "SOMA_RODADAS",
    }
    base.update(overrides)
    return base


async def test_criar_modalidade_com_coordenador_retorna_201(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-1@tjr.app"
    )
    evento_id = await _criar_evento(client, headers)

    resposta = await client.post("/api/v1/modalidades", json=_payload(evento_id), headers=headers)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "RASCUNHO"
    assert corpo["tentativas_por_rodada"] == 1


async def test_criar_modalidade_com_papel_secretaria_retorna_403(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-2@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    headers_secretaria = await _auth_header(
        client, db_session, Papel.SECRETARIA, "secretaria-modalidades@tjr.app"
    )

    resposta = await client.post(
        "/api/v1/modalidades", json=_payload(evento_id), headers=headers_secretaria
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_criar_modalidade_com_niveis_invalidos_retorna_422(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-3@tjr.app"
    )
    evento_id = await _criar_evento(client, headers)

    resposta = await client.post(
        "/api/v1/modalidades",
        json=_payload(evento_id, niveis_aplicaveis=[0, 9]),
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "NIVEIS_APLICAVEIS_INVALIDOS"


async def test_listar_modalidades_filtra_por_evento_id(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-4@tjr.app"
    )
    evento_a = await _criar_evento(client, headers, nome="Evento A")
    evento_b = await _criar_evento(client, headers, nome="Evento B")
    await client.post("/api/v1/modalidades", json=_payload(evento_a, nome="M1"), headers=headers)
    await client.post("/api/v1/modalidades", json=_payload(evento_b, nome="M2"), headers=headers)

    resposta = await client.get(f"/api/v1/modalidades?evento_id={evento_a}", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["nome"] == "M1"


async def test_obter_modalidade_inexistente_retorna_404(client, db_session):
    import uuid

    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-5@tjr.app"
    )

    resposta = await client.get(f"/api/v1/modalidades/{uuid.uuid4()}", headers=headers)

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "MODALIDADE_NAO_ENCONTRADA"


async def test_listar_modalidades_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-7@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    await client.post("/api/v1/modalidades", json=_payload(evento_id), headers=headers_coord)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-modalidades-1@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/modalidades?evento_id={evento_id}", headers=headers_arbitro
    )

    assert resposta.status_code == 200


async def test_obter_modalidade_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-8@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    criada = await client.post(
        "/api/v1/modalidades", json=_payload(evento_id), headers=headers_coord
    )
    modalidade_id = criada.json()["id"]
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-modalidades-2@tjr.app"
    )

    resposta = await client.get(f"/api/v1/modalidades/{modalidade_id}", headers=headers_arbitro)

    assert resposta.status_code == 200


async def test_criar_modalidade_com_papel_arbitro_continua_403(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-9@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-modalidades-3@tjr.app"
    )

    resposta = await client.post(
        "/api/v1/modalidades", json=_payload(evento_id), headers=headers_arbitro
    )

    assert resposta.status_code == 403


async def test_atualizar_modalidade_altera_nome(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-modalidades-6@tjr.app"
    )
    evento_id = await _criar_evento(client, headers)
    criada = await client.post("/api/v1/modalidades", json=_payload(evento_id), headers=headers)
    modalidade_id = criada.json()["id"]

    resposta = await client.patch(
        f"/api/v1/modalidades/{modalidade_id}", json={"nome": "Sumo Avancado"}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Sumo Avancado"
