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


async def _criar_modalidade(client, headers, evento_id, formato_chaveamento):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Combate",
            "tipo_disputa": "CONFRONTO",
            "formato_chaveamento": formato_chaveamento,
            "niveis_aplicaveis": [1, 2],
            "ficha_unica_entre_niveis": False,
            "qtd_rodadas": 5,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return resposta.json()["id"]


async def _criar_equipe_inscrita(client, headers, modalidade_id, nome):
    equipe = await client.post("/api/v1/equipes", json={"nome": nome, "nivel": 1}, headers=headers)
    equipe_id = equipe.json()["id"]
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )
    return equipe_id


async def test_gerar_chaveamento_mata_mata_cria_rodada_1_com_partidas(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "MATA_MATA")
    for i in range(4):
        await _criar_equipe_inscrita(client, headers, modalidade_id, f"Equipe {i}")

    resposta = await client.post(
        "/api/v1/chaveamento/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["numero"] == 1

    partidas = await client.get(f"/api/v1/rodadas/{corpo['id']}/partidas", headers=headers)
    assert len(partidas.json()) == 2


async def test_gerar_chaveamento_com_papel_arbitro_retorna_403(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-chav-2@tjr.app"
    )
    evento_id = await _criar_evento(client, coord_headers)
    modalidade_id = await _criar_modalidade(client, coord_headers, evento_id, "MATA_MATA")
    for i in range(2):
        await _criar_equipe_inscrita(client, coord_headers, modalidade_id, f"Equipe {i}")
    headers_arbitro = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-chav@tjr.app")

    resposta = await client.post(
        "/api/v1/chaveamento/gerar", json={"modalidade_id": modalidade_id}, headers=headers_arbitro
    )

    assert resposta.status_code == 403


async def test_gerar_chaveamento_com_formato_todos_contra_todos_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "TODOS_CONTRA_TODOS")
    for i in range(2):
        await _criar_equipe_inscrita(client, headers, modalidade_id, f"Equipe {i}")

    resposta = await client.post(
        "/api/v1/chaveamento/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "FORMATO_CHAVEAMENTO_INVALIDO_PARA_GERAR"


async def test_resetar_chaveamento_apaga_rodada_e_retorna_204(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-4@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "MATA_MATA")
    for i in range(4):
        await _criar_equipe_inscrita(client, headers, modalidade_id, f"Equipe {i}")
    await client.post(
        "/api/v1/chaveamento/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/reset",
        json={"justificativa": "formato errado, recomecar do zero"},
        headers=headers,
    )

    assert resposta.status_code == 204

    listagem = await client.get(
        "/api/v1/rodadas", params={"modalidade_id": modalidade_id}, headers=headers
    )
    assert listagem.json()["itens"] == []


async def test_resetar_chaveamento_com_papel_arbitro_retorna_403(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-chav-5@tjr.app"
    )
    evento_id = await _criar_evento(client, coord_headers)
    modalidade_id = await _criar_modalidade(client, coord_headers, evento_id, "MATA_MATA")
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-chav-2@tjr.app"
    )

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/reset",
        json={"justificativa": "engano"},
        headers=headers_arbitro,
    )

    assert resposta.status_code == 403


async def test_resetar_chaveamento_em_modalidade_individual_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-6@tjr.app")
    evento_id = await _criar_evento(client, headers)
    resposta_modalidade = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Resgate",
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": [1],
            "ficha_unica_entre_niveis": True,
            "qtd_rodadas": 3,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    modalidade_id = resposta_modalidade.json()["id"]

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/reset",
        json={"justificativa": "engano"},
        headers=headers,
    )

    assert resposta.status_code == 422
