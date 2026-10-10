import uuid

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


async def _montar_cenario(client, headers):
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
            "nome": "Sumo",
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": [1],
            "ficha_unica_entre_niveis": True,
            "qtd_rodadas": 1,
            "duracao_maxima_rodada_seg": 300,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    modalidade_id = modalidade.json()["id"]

    ficha = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade_id}, headers=headers
    )
    ficha_id = ficha.json()["id"]

    grupo = await client.post(
        f"/api/v1/fichas/{ficha_id}/grupos", json={"nome": "Geral", "ordem": 1}, headers=headers
    )
    grupo_id = grupo.json()["id"]

    criterio = await client.post(
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
    criterio_id = criterio.json()["id"]

    rodada = await client.post(
        "/api/v1/rodadas",
        json={"modalidade_id": modalidade_id, "numero": 1, "modo_horario": "AUTOMATICO"},
        headers=headers,
    )
    rodada_id = rodada.json()["id"]

    equipe = await client.post(
        "/api/v1/equipes", json={"nome": "Equipe X", "nivel": 1}, headers=headers
    )
    equipe_id = equipe.json()["id"]

    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )
    await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade_id, "nome": "Arena 1"},
        headers=headers,
    )
    await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": modalidade_id,
            "rodada_ids": [rodada_id],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=headers,
    )

    return {
        "evento_id": evento_id,
        "modalidade_id": modalidade_id,
        "ficha_id": ficha_id,
        "rodada_id": rodada_id,
        "equipe_id": equipe_id,
        "criterio_id": criterio_id,
    }


def _payload(cenario, *, ocorrencias=3, client_operation_id=None):
    return {
        "ficha_id": cenario["ficha_id"],
        "rodada_id": cenario["rodada_id"],
        "tentativa": 1,
        "equipe_id": cenario["equipe_id"],
        "client_operation_id": client_operation_id or str(uuid.uuid4()),
        "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": ocorrencias}],
    }


async def test_criar_lancamento_com_arbitro_retorna_201_e_total_correto(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-1@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-1@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)

    resposta = await client.post(
        "/api/v1/lancamentos", json=_payload(cenario, ocorrencias=3), headers=headers
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["total"] == 30
    assert corpo["status"] == "PENDENTE"


async def test_criar_lancamento_com_ocorrencias_negativas_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-neg@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-neg@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)

    resposta = await client.post(
        "/api/v1/lancamentos", json=_payload(cenario, ocorrencias=-2), headers=headers
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


async def test_criar_lancamento_idempotente_retorna_mesmo_recurso(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-2@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-2@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    operacao_id = str(uuid.uuid4())

    primeira = await client.post(
        "/api/v1/lancamentos",
        json=_payload(cenario, client_operation_id=operacao_id),
        headers=headers,
    )
    segunda = await client.post(
        "/api/v1/lancamentos",
        json=_payload(cenario, client_operation_id=operacao_id),
        headers=headers,
    )

    assert primeira.json()["id"] == segunda.json()["id"]
    assert primeira.status_code == 201
    assert segunda.status_code == 200


async def test_obter_lancamento_traz_itens(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-3@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-3@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=headers)
    lancamento_id = criado.json()["id"]

    resposta = await client.get(f"/api/v1/lancamentos/{lancamento_id}", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["itens"]) == 1
    assert corpo["itens"][0]["pontos"] == 30


async def test_confirmar_lancamento(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-4@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-4@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=headers)
    lancamento_id = criado.json()["id"]

    resposta = await client.post(f"/api/v1/lancamentos/{lancamento_id}/confirmar", headers=headers)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "CONFIRMADO"


async def test_corrigir_lancamento_com_arbitro_retorna_403(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-5@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-5@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=headers)
    lancamento_id = criado.json()["id"]
    await client.post(f"/api/v1/lancamentos/{lancamento_id}/confirmar", headers=headers)

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/corrigir",
        json={
            "justificativa": "Errei a contagem",
            "revision": 1,
            "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": 5}],
        },
        headers=headers,
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_corrigir_lancamento_com_coordenador_atualiza_total(client, db_session):
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-6@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-6@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post(
        "/api/v1/lancamentos", json=_payload(cenario, ocorrencias=3), headers=arbitro_headers
    )
    lancamento_id = criado.json()["id"]
    await client.post(f"/api/v1/lancamentos/{lancamento_id}/confirmar", headers=arbitro_headers)

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/corrigir",
        json={
            "justificativa": "Errei a contagem",
            "revision": 1,
            "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": 5}],
        },
        headers=coord_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 50
    assert corpo["revision"] == 2


async def test_corrigir_lancamento_sem_justificativa_e_aceita(client, db_session):
    # Justificativa e opcional (pedido explicito do cliente, 2026-08-25) --
    # nao bloqueia mais a correcao quando vem em branco.
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-7@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-7@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post(
        "/api/v1/lancamentos", json=_payload(cenario), headers=arbitro_headers
    )
    lancamento_id = criado.json()["id"]
    await client.post(f"/api/v1/lancamentos/{lancamento_id}/confirmar", headers=arbitro_headers)

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/corrigir",
        json={
            "justificativa": "",
            "revision": 1,
            "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": 5}],
        },
        headers=coord_headers,
    )

    assert resposta.status_code == 200
    assert resposta.json()["revision"] == 2


async def test_corrigir_lancamento_com_revision_desatualizada_retorna_409(client, db_session):
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-8@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-8@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post(
        "/api/v1/lancamentos", json=_payload(cenario, ocorrencias=3), headers=arbitro_headers
    )
    lancamento_id = criado.json()["id"]
    await client.post(f"/api/v1/lancamentos/{lancamento_id}/confirmar", headers=arbitro_headers)

    await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/corrigir",
        json={
            "justificativa": "Primeira correcao",
            "revision": 1,
            "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": 4}],
        },
        headers=coord_headers,
    )

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/corrigir",
        json={
            "justificativa": "Segunda correcao, concorrente e desatualizada",
            "revision": 1,
            "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": 9}],
        },
        headers=coord_headers,
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "LANCAMENTO_REVISION_DESATUALIZADA"


async def test_listar_lancamentos_filtra_por_rodada(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-lanc-8@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-8@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=headers)

    resposta = await client.get(
        f"/api/v1/lancamentos?rodada_id={cenario['rodada_id']}", headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1


async def test_listar_auditoria_com_coordenador_traz_lancamento_enriquecido(client, db_session):
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-9@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-9@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    await client.post(
        "/api/v1/lancamentos", json=_payload(cenario, ocorrencias=3), headers=arbitro_headers
    )

    resposta = await client.get(
        f"/api/v1/lancamentos/auditoria?evento_id={cenario['evento_id']}", headers=coord_headers
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    item = corpo["itens"][0]
    assert item["modalidade_nome"] == "Sumo"
    assert item["equipe_nome"] == "Equipe X"
    assert item["total"] == 30
    assert len(item["itens"]) == 1


async def test_listar_auditoria_filtra_por_modalidade(client, db_session):
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-11@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-11@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=arbitro_headers)

    modalidade2 = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": cenario["evento_id"],
            "nome": "Danca",
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": [1],
            "ficha_unica_entre_niveis": True,
            "qtd_rodadas": 1,
            "duracao_maxima_rodada_seg": 300,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=coord_headers,
    )
    modalidade2_id = modalidade2.json()["id"]
    ficha2 = await client.post(
        "/api/v1/fichas", json={"modalidade_id": modalidade2_id}, headers=coord_headers
    )
    ficha2_id = ficha2.json()["id"]
    grupo2 = await client.post(
        f"/api/v1/fichas/{ficha2_id}/grupos",
        json={"nome": "Geral", "ordem": 1},
        headers=coord_headers,
    )
    criterio2 = await client.post(
        f"/api/v1/grupos/{grupo2.json()['id']}/criterios",
        json={
            "nome": "Nota",
            "categoria": "PONTUACAO",
            "tipo": "CONTADOR",
            "pontos": 5,
            "ordem": 1,
        },
        headers=coord_headers,
    )
    rodada2 = await client.post(
        "/api/v1/rodadas",
        json={"modalidade_id": modalidade2_id, "numero": 1, "modo_horario": "AUTOMATICO"},
        headers=coord_headers,
    )
    equipe2 = await client.post(
        "/api/v1/equipes", json={"nome": "Equipe Y", "nivel": 1}, headers=coord_headers
    )
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe2.json()["id"], "modalidade_id": modalidade2_id},
        headers=coord_headers,
    )
    await client.post(
        "/api/v1/arenas",
        json={"modalidade_id": modalidade2_id, "nome": "Arena 1"},
        headers=coord_headers,
    )
    await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": modalidade2_id,
            "rodada_ids": [rodada2.json()["id"]],
            "horario_inicio": "2026-08-10T08:00:00Z",
        },
        headers=coord_headers,
    )
    await client.post(
        "/api/v1/lancamentos",
        json={
            "ficha_id": ficha2_id,
            "rodada_id": rodada2.json()["id"],
            "tentativa": 1,
            "equipe_id": equipe2.json()["id"],
            "client_operation_id": str(uuid.uuid4()),
            "itens": [{"criterio_id": criterio2.json()["id"], "ocorrencias": 1}],
        },
        headers=arbitro_headers,
    )

    resposta = await client.get(
        f"/api/v1/lancamentos/auditoria?evento_id={cenario['evento_id']}"
        f"&modalidade_id={modalidade2_id}",
        headers=coord_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["modalidade_nome"] == "Danca"


async def test_listar_auditoria_filtra_por_rodada(client, db_session):
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-12@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-12@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=arbitro_headers)

    await client.patch(
        f"/api/v1/modalidades/{cenario['modalidade_id']}",
        json={"qtd_rodadas": 2},
        headers=coord_headers,
    )
    rodada2 = await client.post(
        "/api/v1/rodadas",
        json={"modalidade_id": cenario["modalidade_id"], "numero": 2, "modo_horario": "AUTOMATICO"},
        headers=coord_headers,
    )
    await client.post(
        "/api/v1/agendamentos/gerar",
        json={
            "modalidade_id": cenario["modalidade_id"],
            "rodada_ids": [rodada2.json()["id"]],
            "horario_inicio": "2026-08-10T09:00:00Z",
        },
        headers=coord_headers,
    )
    await client.post(
        "/api/v1/lancamentos",
        json={
            "ficha_id": cenario["ficha_id"],
            "rodada_id": rodada2.json()["id"],
            "tentativa": 1,
            "equipe_id": cenario["equipe_id"],
            "client_operation_id": str(uuid.uuid4()),
            "itens": [{"criterio_id": cenario["criterio_id"], "ocorrencias": 1}],
        },
        headers=arbitro_headers,
    )

    resposta = await client.get(
        f"/api/v1/lancamentos/auditoria?evento_id={cenario['evento_id']}"
        f"&rodada_id={cenario['rodada_id']}",
        headers=coord_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["rodada_numero"] == 1


async def test_listar_auditoria_filtra_por_equipe_sem_informar_evento_id(client, db_session):
    arbitro_headers = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-lanc-13@tjr.app"
    )
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-13@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=arbitro_headers)

    resposta = await client.get(
        f"/api/v1/lancamentos/auditoria?equipe_id={cenario['equipe_id']}",
        headers=coord_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["equipe_nome"] == "Equipe X"


async def test_listar_auditoria_com_papel_publico_retorna_403(client, db_session):
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-lanc-10@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)

    resposta = await client.get(f"/api/v1/lancamentos/auditoria?evento_id={cenario['evento_id']}")

    assert resposta.status_code == 401


async def _lancamento_confirmado(client, db_session, sufixo):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, f"arb-anular-{sufixo}@tjr.app")
    coord_headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, f"coord-anular-{sufixo}@tjr.app"
    )
    cenario = await _montar_cenario(client, coord_headers)
    criado = await client.post("/api/v1/lancamentos", json=_payload(cenario), headers=headers)
    lancamento_id = criado.json()["id"]
    await client.post(f"/api/v1/lancamentos/{lancamento_id}/confirmar", headers=headers)
    return headers, coord_headers, lancamento_id


async def test_anular_lancamento_com_coordenador_retorna_anulado(client, db_session):
    _, coord_headers, lancamento_id = await _lancamento_confirmado(client, db_session, 1)

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/anular",
        json={"justificativa": "Pontuou a equipe errada"},
        headers=coord_headers,
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ANULADO"


async def test_anular_lancamento_sem_justificativa_retorna_422(client, db_session):
    _, coord_headers, lancamento_id = await _lancamento_confirmado(client, db_session, 2)

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/anular",
        json={"justificativa": "   "},
        headers=coord_headers,
    )

    assert resposta.status_code == 422


async def test_anular_lancamento_com_arbitro_retorna_403(client, db_session):
    headers, _, lancamento_id = await _lancamento_confirmado(client, db_session, 3)

    resposta = await client.post(
        f"/api/v1/lancamentos/{lancamento_id}/anular",
        json={"justificativa": "x"},
        headers=headers,
    )

    assert resposta.status_code == 403
