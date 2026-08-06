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


async def _criar_evento_e_modalidade(client, headers, *, ficha_unica_entre_niveis=False):
    evento = await client.post(
        "/api/v1/eventos",
        json={
            "nome": "TJR 2026",
            "ano": 2026,
            "data_inicio": "2026-03-10",
            "data_fim": "2026-03-12",
        },
        headers=headers,
    )
    evento_id = evento.json()["id"]

    modalidade = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Sumo de Robos",
            "tipo_disputa": "CONFRONTO",
            "niveis_aplicaveis": [1, 2],
            "ficha_unica_entre_niveis": ficha_unica_entre_niveis,
            "qtd_rodadas": 3,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return modalidade.json()["id"]


async def test_criar_ficha_sem_token_retorna_401(client):
    resposta = await client.post("/api/v1/fichas", json={"modalidade_id": "x"})

    assert resposta.status_code == 401


async def test_fluxo_completo_ficha_grupo_criterio_e_simulacao(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-fichas-1@tjr.app")
    modalidade_id = await _criar_evento_e_modalidade(client, headers)

    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers
    )
    assert ficha_resp.status_code == 201
    ficha_id = ficha_resp.json()["id"]
    assert ficha_resp.json()["status"] == "RASCUNHO"

    grupo_resp = await client.post(
        f"/api/v1/fichas/{ficha_id}/grupos",
        json={"nome": "Parte Tecnica", "ordem": 1},
        headers=headers,
    )
    assert grupo_resp.status_code == 201
    grupo_id = grupo_resp.json()["id"]

    criterio_resp = await client.post(
        f"/api/v1/grupos/{grupo_id}/criterios",
        json={
            "nome": "Lombada",
            "categoria": "PONTUACAO",
            "tipo": "CONTADOR",
            "pontos": 10,
            "ordem": 1,
        },
        headers=headers,
    )
    assert criterio_resp.status_code == 201
    criterio_id = criterio_resp.json()["id"]

    obter_resp = await client.get(f"/api/v1/fichas/{ficha_id}", headers=headers)
    assert obter_resp.status_code == 200
    corpo = obter_resp.json()
    assert corpo["grupos"][0]["criterios"][0]["nome"] == "Lombada"

    publicar_resp = await client.post(f"/api/v1/fichas/{ficha_id}/publicar", headers=headers)
    assert publicar_resp.status_code == 200
    assert publicar_resp.json()["status"] == "PUBLICADA"

    simular_resp = await client.post(
        f"/api/v1/fichas/{ficha_id}/simular",
        json={"valores": [{"criterio_id": criterio_id, "ocorrencias": 3}]},
        headers=headers,
    )
    assert simular_resp.status_code == 200
    assert simular_resp.json()["total"] == 30


async def test_editar_criterio_apos_publicar_cria_nova_versao(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-fichas-2@tjr.app")
    modalidade_id = await _criar_evento_e_modalidade(client, headers)

    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers
    )
    ficha_id = ficha_resp.json()["id"]
    grupo_resp = await client.post(
        f"/api/v1/fichas/{ficha_id}/grupos", json={"nome": "Grupo", "ordem": 1}, headers=headers
    )
    grupo_id = grupo_resp.json()["id"]
    criterio_resp = await client.post(
        f"/api/v1/grupos/{grupo_id}/criterios",
        json={
            "nome": "Lombada",
            "categoria": "PONTUACAO",
            "tipo": "CONTADOR",
            "pontos": 10,
            "ordem": 1,
        },
        headers=headers,
    )
    criterio_id = criterio_resp.json()["id"]
    await client.post(f"/api/v1/fichas/{ficha_id}/publicar", headers=headers)

    atualizado_resp = await client.patch(
        f"/api/v1/criterios/{criterio_id}", json={"pontos": 20}, headers=headers
    )

    assert atualizado_resp.status_code == 200
    assert atualizado_resp.json()["pontos"] == 20
    assert atualizado_resp.json()["id"] != criterio_id

    ficha_antiga_resp = await client.get(f"/api/v1/fichas/{ficha_id}", headers=headers)
    assert ficha_antiga_resp.json()["status"] == "SUBSTITUIDA"


async def test_criar_ficha_com_nivel_invalido_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-fichas-3@tjr.app")
    modalidade_id = await _criar_evento_e_modalidade(client, headers, ficha_unica_entre_niveis=True)

    resposta = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "FICHA_NIVEL_NAO_PERMITIDO"


async def test_simular_com_escala_invalida_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-fichas-4@tjr.app")
    modalidade_id = await _criar_evento_e_modalidade(client, headers)
    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers
    )
    ficha_id = ficha_resp.json()["id"]
    grupo_resp = await client.post(
        f"/api/v1/fichas/{ficha_id}/grupos", json={"nome": "Grupo", "ordem": 1}, headers=headers
    )
    grupo_id = grupo_resp.json()["id"]
    criterio_resp = await client.post(
        f"/api/v1/grupos/{grupo_id}/criterios",
        json={
            "nome": "Nota Artistica",
            "categoria": "PONTUACAO",
            "tipo": "ESCALA",
            "valores_permitidos": [0, 5, 10],
            "ordem": 1,
        },
        headers=headers,
    )
    criterio_id = criterio_resp.json()["id"]

    resposta = await client.post(
        f"/api/v1/fichas/{ficha_id}/simular",
        json={"valores": [{"criterio_id": criterio_id, "valor": 3}]},
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "CRITERIO_VALOR_FORA_DA_ESCALA"


async def test_listar_fichas_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-fichas-6@tjr.app"
    )
    modalidade_id = await _criar_evento_e_modalidade(client, headers_coord)
    await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers_coord
    )
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-fichas-2@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/fichas?modalidade_id={modalidade_id}", headers=headers_arbitro
    )

    assert resposta.status_code == 200


async def test_obter_ficha_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-fichas-7@tjr.app"
    )
    modalidade_id = await _criar_evento_e_modalidade(client, headers_coord)
    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers_coord
    )
    ficha_id = ficha_resp.json()["id"]
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-fichas-3@tjr.app"
    )

    resposta = await client.get(f"/api/v1/fichas/{ficha_id}", headers=headers_arbitro)

    assert resposta.status_code == 200


async def test_criar_ficha_com_papel_arbitro_continua_403(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-fichas-8@tjr.app"
    )
    modalidade_id = await _criar_evento_e_modalidade(client, headers_coord)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-fichas-4@tjr.app"
    )

    resposta = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers_arbitro
    )

    assert resposta.status_code == 403


async def test_excluir_ficha_sem_lancamentos_retorna_204(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-fichas-9@tjr.app")
    modalidade_id = await _criar_evento_e_modalidade(client, headers)
    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers
    )
    ficha_id = ficha_resp.json()["id"]

    resposta = await client.delete(f"/api/v1/fichas/{ficha_id}", headers=headers)

    assert resposta.status_code == 204
    obter_resp = await client.get(f"/api/v1/fichas/{ficha_id}", headers=headers)
    assert obter_resp.status_code == 404


async def test_excluir_ficha_com_papel_arbitro_retorna_403(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-fichas-10@tjr.app"
    )
    modalidade_id = await _criar_evento_e_modalidade(client, headers_coord)
    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers_coord
    )
    ficha_id = ficha_resp.json()["id"]
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-fichas-5@tjr.app"
    )

    resposta = await client.delete(f"/api/v1/fichas/{ficha_id}", headers=headers_arbitro)

    assert resposta.status_code == 403


async def test_depreciar_ficha_publicada_retorna_200(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-fichas-11@tjr.app")
    modalidade_id = await _criar_evento_e_modalidade(client, headers)
    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers
    )
    ficha_id = ficha_resp.json()["id"]
    await client.post(f"/api/v1/fichas/{ficha_id}/publicar", headers=headers)

    resposta = await client.post(f"/api/v1/fichas/{ficha_id}/depreciar", headers=headers)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "DEPRECADA"


async def test_deletar_grupo_com_papel_arbitro_retorna_403(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-fichas-5@tjr.app"
    )
    modalidade_id = await _criar_evento_e_modalidade(client, headers_coord)
    ficha_resp = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id, "nivel": 1}, headers=headers_coord
    )
    ficha_id = ficha_resp.json()["id"]
    grupo_resp = await client.post(
        f"/api/v1/fichas/{ficha_id}/grupos",
        json={"nome": "Grupo", "ordem": 1},
        headers=headers_coord,
    )
    grupo_id = grupo_resp.json()["id"]

    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-fichas@tjr.app"
    )

    resposta = await client.delete(f"/api/v1/grupos/{grupo_id}", headers=headers_arbitro)

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"
