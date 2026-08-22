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


async def _criar_modalidade(client, headers, evento_id, *, duracao_maxima_rodada_seg=300):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Resgate no Plano",
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": [1],
            "ficha_unica_entre_niveis": True,
            "qtd_rodadas": 2,
            "duracao_maxima_rodada_seg": duracao_maxima_rodada_seg,
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


async def _preparar_cenario(client, headers):
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id)
    rodada = await client.post(
        "/api/v1/rodadas",
        json={"modalidade_id": modalidade_id, "numero": 1, "modo_horario": "AUTOMATICO"},
        headers=headers,
    )
    rodada_id = rodada.json()["id"]
    await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=headers,
    )
    equipe_id = await _criar_equipe_inscrita(client, headers, modalidade_id)
    return {
        "modalidade_id": modalidade_id,
        "rodada_id": rodada_id,
        "equipe_id": equipe_id,
    }


async def test_gerar_agendamento_com_coordenador_retorna_200_e_lista(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-agenda-1@tjr.app")
    cenario = await _preparar_cenario(client, headers)

    resposta = await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": cenario["modalidade_id"],
            "rodada_ids": [cenario["rodada_id"]],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["equipe_id"] == cenario["equipe_id"]
    assert corpo[0]["ordem_na_arena"] == 0


async def test_gerar_agendamento_com_arbitro_retorna_403(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-agenda-2@tjr.app"
    )
    cenario = await _preparar_cenario(client, coord_headers)
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-agenda-1@tjr.app"
    )

    resposta = await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": cenario["modalidade_id"],
            "rodada_ids": [cenario["rodada_id"]],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=arbitro_headers,
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_gerar_agendamento_sem_regenerar_em_cima_de_existente_retorna_409(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-agenda-3@tjr.app")
    cenario = await _preparar_cenario(client, headers)
    payload = {
        "modalidade_id": cenario["modalidade_id"],
        "rodada_ids": [cenario["rodada_id"]],
        "horario_inicio": "2026-08-10T08:00:00Z",
    }
    await client.post("/api/v1/agendamentos/gerar", json=payload, headers=headers)

    resposta = await client.post("/api/v1/agendamentos/gerar", json=payload, headers=headers)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "AGENDAMENTO_JA_EXISTE"


async def test_listar_agendamentos_filtra_por_modalidade(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-agenda-4@tjr.app")
    cenario = await _preparar_cenario(client, headers)
    await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": cenario["modalidade_id"],
            "rodada_ids": [cenario["rodada_id"]],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=headers,
    )

    resposta = await client.get(
        f"/api/v1/agendamentos?modalidade_id={cenario['modalidade_id']}", headers=headers
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["equipe_id"] == cenario["equipe_id"]


async def test_estimar_horarios_sem_confirmacao_devolve_horario_planejado(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-agenda-5@tjr.app")
    cenario = await _preparar_cenario(client, headers)
    gerado = await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": cenario["modalidade_id"],
            "rodada_ids": [cenario["rodada_id"]],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=headers,
    )
    agendamento_id = gerado.json()[0]["id"]

    resposta = await client.get(
        f"/api/v1/agendamentos/estimativa?modalidade_id={cenario['modalidade_id']}",
        headers=headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["agendamento_id"] == agendamento_id
    assert corpo[0]["horario_previsto"] == "2026-08-10T08:00:00Z"


async def test_estimar_horarios_com_arbitro_retorna_200(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-agenda-6@tjr.app"
    )
    cenario = await _preparar_cenario(client, coord_headers)
    await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": cenario["modalidade_id"],
            "rodada_ids": [cenario["rodada_id"]],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=coord_headers,
    )
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-agenda-2@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/agendamentos/estimativa?modalidade_id={cenario['modalidade_id']}",
        headers=arbitro_headers,
    )

    assert resposta.status_code == 200
