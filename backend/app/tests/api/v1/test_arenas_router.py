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


async def _criar_modalidade(client, headers, evento_id, tipo_disputa="INDIVIDUAL"):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Resgate no Plano",
            "tipo_disputa": tipo_disputa,
            "niveis_aplicaveis": [1, 2],
            "ficha_unica_entre_niveis": True,
            "qtd_rodadas": 2,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return resposta.json()["id"]


async def test_criar_arena_com_coordenador_retorna_201(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-arena-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)

    resposta = await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Arena 1"
    assert corpo["ativo"] is True


async def test_criar_arena_com_arbitro_retorna_403(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-arena-2@tjr.app"
    )
    evento_id = await _criar_evento(client, coord_headers)
    modalidade_id = await _criar_modalidade(client, coord_headers, evento_id)
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-arena-1@tjr.app"
    )

    resposta = await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=arbitro_headers,
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_criar_arena_em_modalidade_confronto_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-arena-3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, tipo_disputa="CONFRONTO")

    resposta = await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "MODALIDADE_NAO_E_INDIVIDUAL"


async def test_listar_arenas_com_arbitro_retorna_200(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-arena-4@tjr.app"
    )
    evento_id = await _criar_evento(client, coord_headers)
    modalidade_id = await _criar_modalidade(client, coord_headers, evento_id)
    await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=coord_headers,
    )
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-arena-2@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/arenas?modalidade_id={modalidade_id}", headers=arbitro_headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1


async def test_atualizar_arena_com_coordenador_desativa(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-arena-5@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)
    criada = await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=headers,
    )
    arena_id = criada.json()["id"]

    resposta = await client.patch(
        f"/api/v1/arenas/{arena_id}", json={"ativo": False}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["ativo"] is False
