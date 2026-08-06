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


async def _criar_modalidade(client, headers, evento_id, qtd_rodadas=3, nome="Sumo"):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": nome,
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": [1, 2],
            "ficha_unica_entre_niveis": False,
            "qtd_rodadas": qtd_rodadas,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return resposta.json()["id"]


def _payload(modalidade_id, **overrides):
    base = {
        "modalidade_id": modalidade_id,
        "numero": 1,
        "modo_horario": "MANUAL",
        "horario_inicio": "2026-03-10T09:00:00Z",
    }
    base.update(overrides)
    return base


async def test_criar_rodada_retorna_201(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-rodada-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)

    resposta = await client.post("/api/v1/rodadas", json=_payload(modalidade_id), headers=headers)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "AGENDADA"
    assert corpo["numero"] == 1


async def test_criar_rodada_manual_sem_horario_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-rodada-2@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)

    resposta = await client.post(
        "/api/v1/rodadas",
        json=_payload(modalidade_id, horario_inicio=None),
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "HORARIO_INICIO_OBRIGATORIO"


async def test_criar_rodada_numero_duplicado_retorna_409(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-rodada-3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)
    await client.post("/api/v1/rodadas", json=_payload(modalidade_id), headers=headers)

    resposta = await client.post("/api/v1/rodadas", json=_payload(modalidade_id), headers=headers)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "RODADA_NUMERO_DUPLICADO"


async def test_listar_rodadas_ordenadas_por_numero(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-rodada-4@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)
    await client.post("/api/v1/rodadas", json=_payload(modalidade_id, numero=2), headers=headers)
    await client.post("/api/v1/rodadas", json=_payload(modalidade_id, numero=1), headers=headers)

    resposta = await client.get(f"/api/v1/rodadas?modalidade_id={modalidade_id}", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [item["numero"] for item in corpo["itens"]] == [1, 2]


async def test_listar_rodadas_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-rodada-6@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    modalidade_id = await _criar_modalidade(client, headers_coord, evento_id)
    await client.post("/api/v1/rodadas", json=_payload(modalidade_id), headers=headers_coord)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-rodada-1@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/rodadas?modalidade_id={modalidade_id}", headers=headers_arbitro
    )

    assert resposta.status_code == 200


async def test_obter_rodada_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-rodada-7@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    modalidade_id = await _criar_modalidade(client, headers_coord, evento_id)
    criada = await client.post(
        "/api/v1/rodadas", json=_payload(modalidade_id), headers=headers_coord
    )
    rodada_id = criada.json()["id"]
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-rodada-2@tjr.app"
    )

    resposta = await client.get(f"/api/v1/rodadas/{rodada_id}", headers=headers_arbitro)

    assert resposta.status_code == 200


async def test_criar_rodada_com_papel_arbitro_continua_403(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-rodada-8@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    modalidade_id = await _criar_modalidade(client, headers_coord, evento_id)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-rodada-3@tjr.app"
    )

    resposta = await client.post(
        "/api/v1/rodadas", json=_payload(modalidade_id), headers=headers_arbitro
    )

    assert resposta.status_code == 403


async def test_atualizar_rodada_altera_status(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-rodada-5@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)
    criada = await client.post("/api/v1/rodadas", json=_payload(modalidade_id), headers=headers)
    rodada_id = criada.json()["id"]

    resposta = await client.patch(
        f"/api/v1/rodadas/{rodada_id}", json={"status": "EM_ANDAMENTO"}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "EM_ANDAMENTO"
