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


async def _criar_modalidade(client, headers, evento_id, tipo_disputa="CONFRONTO", qtd_rodadas=2):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Sumo",
            "tipo_disputa": tipo_disputa,
            "niveis_aplicaveis": [1, 2],
            "ficha_unica_entre_niveis": False,
            "qtd_rodadas": qtd_rodadas,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return resposta.json()["id"]


async def _criar_equipe_inscrita(client, headers, modalidade_id, nivel=1, nome="Equipe X"):
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


async def test_gerar_rodadas_cria_todas_de_uma_vez(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-gerar-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(
        client, headers, evento_id, tipo_disputa="INDIVIDUAL", qtd_rodadas=3
    )

    resposta = await client.post(
        "/api/v1/rodadas/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [r["numero"] for r in corpo] == [1, 2, 3]


async def test_gerar_rodadas_confronto_traz_partidas_pareadas(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-gerar-2@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(
        client, headers, evento_id, tipo_disputa="CONFRONTO", qtd_rodadas=1
    )
    for i in range(4):
        await _criar_equipe_inscrita(client, headers, modalidade_id, nome=f"Equipe {i}")

    await client.post(
        "/api/v1/rodadas/gerar", json={"modalidade_id": modalidade_id}, headers=headers
    )

    rodadas = await client.get(f"/api/v1/rodadas?modalidade_id={modalidade_id}", headers=headers)
    rodada_id = rodadas.json()["itens"][0]["id"]

    partidas = await client.get(f"/api/v1/rodadas/{rodada_id}/partidas", headers=headers)

    assert partidas.status_code == 200
    assert len(partidas.json()) == 2
