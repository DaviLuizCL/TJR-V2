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


async def test_criar_partida_manual_cria_partida_na_rodada_1(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-man1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "MATA_MATA")
    equipe_a = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe A")
    equipe_b = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe B")

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        json={"equipe_a_id": equipe_a, "equipe_b_id": equipe_b},
        headers=headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert {corpo["equipe_a_id"], corpo["equipe_b_id"]} == {equipe_a, equipe_b}
    assert corpo["status"] == "AGENDADA"


async def test_criar_partida_manual_com_papel_arbitro_retorna_403(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-chav-man2@tjr.app"
    )
    evento_id = await _criar_evento(client, coord_headers)
    modalidade_id = await _criar_modalidade(client, coord_headers, evento_id, "MATA_MATA")
    equipe_a = await _criar_equipe_inscrita(client, coord_headers, modalidade_id, "Equipe A")
    equipe_b = await _criar_equipe_inscrita(client, coord_headers, modalidade_id, "Equipe B")
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-chav-man@tjr.app"
    )

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        json={"equipe_a_id": equipe_a, "equipe_b_id": equipe_b},
        headers=headers_arbitro,
    )

    assert resposta.status_code == 403


async def test_criar_partida_manual_com_niveis_diferentes_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-man3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "MATA_MATA")
    equipe_a = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe A", nivel=1)
    equipe_b = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe B", nivel=2)

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        json={"equipe_a_id": equipe_a, "equipe_b_id": equipe_b},
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "NIVEIS_INCOMPATIVEIS"


async def test_criar_partida_manual_com_bye_fecha_a_partida_sozinha(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-man4@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "MATA_MATA")
    equipe_a = await _criar_equipe_inscrita(client, headers, modalidade_id, "Equipe A")

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        json={"equipe_a_id": equipe_a, "equipe_b_id": None},
        headers=headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["equipe_b_id"] is None
    assert corpo["status"] == "ENCERRADA"
    assert corpo["vencedor_id"] == equipe_a


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


async def test_gerar_chaveamento_com_formato_todos_contra_todos_explicito_cria_returno(
    client, db_session
):
    # /chaveamento/gerar virou o ponto de entrada unico pra CONFRONTO (antes
    # so aceitava MATA_MATA, e TODOS_CONTRA_TODOS explicito tinha que passar
    # por /rodadas/gerar) -- com o formato forcado na modalidade, gera o
    # returno pra todos os niveis igual, sem olhar contagem de equipe.
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, "TODOS_CONTRA_TODOS")
    for i in range(2):
        await _criar_equipe_inscrita(client, headers, modalidade_id, f"Equipe {i}")

    resposta = await client.post(
        "/api/v1/chaveamento/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["numero"] == 1

    partidas = await client.get(f"/api/v1/rodadas/{corpo['id']}/partidas", headers=headers)
    assert len(partidas.json()) == 1


async def test_gerar_chaveamento_automatico_decide_formato_por_nivel_pela_contagem(
    client, db_session
):
    # formato_chaveamento=None na modalidade = decisao automatica por nivel:
    # <=5 equipes = todos-contra-todos, 6+ = mata-mata. Nivel 1 (3 equipes) e
    # nivel 2 (6 equipes) na MESMA modalidade, cada um com o formato certo.
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-chav-7@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, None)
    for i in range(3):
        await _criar_equipe_inscrita(client, headers, modalidade_id, f"N1 Equipe {i}", nivel=1)
    for i in range(6):
        await _criar_equipe_inscrita(client, headers, modalidade_id, f"N2 Equipe {i}", nivel=2)

    resposta = await client.post(
        "/api/v1/chaveamento/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    assert resposta.status_code == 201

    rodadas = await client.get(
        "/api/v1/rodadas", params={"modalidade_id": modalidade_id}, headers=headers
    )
    partidas_por_nivel = {1: [], 2: []}
    for rodada in rodadas.json()["itens"]:
        resposta_partidas = await client.get(
            f"/api/v1/rodadas/{rodada['id']}/partidas", headers=headers
        )
        for partida in resposta_partidas.json():
            partidas_por_nivel[partida["nivel"]].append(partida)

    assert partidas_por_nivel[1]
    assert all(p["formato_chaveamento"] == "TODOS_CONTRA_TODOS" for p in partidas_por_nivel[1])
    assert partidas_por_nivel[2]
    assert all(p["formato_chaveamento"] == "MATA_MATA" for p in partidas_por_nivel[2])


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
