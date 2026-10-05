from app.models.usuario import Papel


async def _criar_usuario(db_session, *, email, papel, senha="senha-123"):
    from app.core.security import hash_senha
    from app.models.usuario import Usuario

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


async def _criar_modalidade_confronto(client, headers, evento_id):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Combate",
            "tipo_disputa": "CONFRONTO",
            "formato_chaveamento": None,
            "niveis_aplicaveis": [1, 2],
            "ficha_unica_entre_niveis": False,
            "qtd_rodadas": 5,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return resposta.json()["id"]


async def _criar_equipe_inscrita(client, headers, modalidade_id, nome, nivel=1):
    equipe = await client.post(
        "/api/v1/equipes", json={"nome": nome, "nivel": nivel}, headers=headers
    )
    equipe_id = equipe.json()["id"]
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )
    return equipe_id


async def test_criar_chave_exige_papel_coordenador(client, db_session):
    coord_headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-1@tjr.app")
    evento_id = await _criar_evento(client, coord_headers)
    modalidade_id = await _criar_modalidade_confronto(client, coord_headers, evento_id)
    headers_arbitro = await _auth_header(client, db_session, Papel.ARBITRO, "arb-chr-1@tjr.app")

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaves",
        json={"modalidade_id": modalidade_id, "nivel": 1, "nome": "Chave A"},
        headers=headers_arbitro,
    )

    assert resposta.status_code == 403


async def test_criar_chave_e_listar(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-2@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)
    equipe_a = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe A")
    equipe_b = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe B")

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaves",
        json={"modalidade_id": modalidade_id, "nivel": 1, "nome": "Chave A"},
        headers=headers,
    )
    assert resposta.status_code == 201
    chave_id = resposta.json()["id"]

    await client.post(
        f"/api/v1/chaves/{chave_id}/equipes", json={"equipe_id": equipe_a}, headers=headers
    )
    await client.post(
        f"/api/v1/chaves/{chave_id}/equipes", json={"equipe_id": equipe_b}, headers=headers
    )

    listagem = await client.get(f"/api/v1/modalidades/{modalidade_id}/chaves", headers=headers)
    assert listagem.status_code == 200
    corpo = listagem.json()
    assert len(corpo) == 1
    assert set(corpo[0]["equipe_ids"]) == {equipe_a, equipe_b}


async def test_listar_chaves_papeis_leitura_ok(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)
    headers_secretaria = await _auth_header(
        client, db_session, Papel.SECRETARIA, "sec-chr-3@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/modalidades/{modalidade_id}/chaves", headers=headers_secretaria
    )

    assert resposta.status_code == 200


async def test_adicionar_equipe_com_nivel_diferente_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-4@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)
    equipe_nivel_2 = await _criar_equipe_inscrita(
        client, headers, modalidade_id, "Equipe Nivel 2", nivel=2
    )
    chave = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaves",
        json={"modalidade_id": modalidade_id, "nivel": 1, "nome": "Chave A"},
        headers=headers,
    )
    chave_id = chave.json()["id"]

    resposta = await client.post(
        f"/api/v1/chaves/{chave_id}/equipes", json={"equipe_id": equipe_nivel_2}, headers=headers
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "NIVEIS_INCOMPATIVEIS"


async def test_remover_equipe_da_chave(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-5@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)
    equipe_a = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe A")
    chave = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaves",
        json={"modalidade_id": modalidade_id, "nivel": 1, "nome": "Chave A"},
        headers=headers,
    )
    chave_id = chave.json()["id"]
    await client.post(
        f"/api/v1/chaves/{chave_id}/equipes", json={"equipe_id": equipe_a}, headers=headers
    )

    resposta = await client.delete(f"/api/v1/chaves/{chave_id}/equipes/{equipe_a}", headers=headers)

    assert resposta.status_code == 204
    listagem = await client.get(f"/api/v1/modalidades/{modalidade_id}/chaves", headers=headers)
    assert listagem.json()[0]["equipe_ids"] == []


async def test_partida_manual_de_fase_de_grupos_herda_a_chave_das_equipes(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-6@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)
    equipe_a = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe A")
    equipe_b = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe B")
    chave = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaves",
        json={"modalidade_id": modalidade_id, "nivel": 1, "nome": "Chave A"},
        headers=headers,
    )
    chave_id = chave.json()["id"]
    for equipe in (equipe_a, equipe_b):
        await client.post(
            f"/api/v1/chaves/{chave_id}/equipes", json={"equipe_id": equipe}, headers=headers
        )

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        json={
            "equipe_a_id": equipe_a,
            "equipe_b_id": equipe_b,
            "rodada_numero": 1,
            "formato_chaveamento": "TODOS_CONTRA_TODOS",
        },
        headers=headers,
    )

    assert resposta.status_code == 201
    assert resposta.json()["chave_id"] == chave_id


async def test_gerar_fase_de_grupos_automatico_nao_existe_mais(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-6b@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/fase-de-grupos/gerar", headers=headers
    )

    assert resposta.status_code in (404, 405)


async def test_get_classificacao_chave_rejeita_papel_publico_via_ranking_privado(
    client, db_session
):
    # Nao existe papel PUBLICO autenticavel via login (sem senha/conta) -- o
    # jeito real de "publico" bater nessa rota e sem header nenhum.
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chr-7@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade_confronto(client, headers, evento_id)
    chave = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaves",
        json={"modalidade_id": modalidade_id, "nivel": 1, "nome": "Chave A"},
        headers=headers,
    )
    chave_id = chave.json()["id"]

    resposta_sem_auth = await client.get(f"/api/v1/chaves/{chave_id}/classificacao")
    assert resposta_sem_auth.status_code == 401

    resposta_coordenador = await client.get(
        f"/api/v1/chaves/{chave_id}/classificacao", headers=headers
    )
    assert resposta_coordenador.status_code == 200
