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


async def _criar_modalidade(client, headers, evento_id, niveis_aplicaveis, nome="Sumo"):
    resposta = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": nome,
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": niveis_aplicaveis,
            "ficha_unica_entre_niveis": False,
            "qtd_rodadas": 2,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    return resposta.json()["id"]


async def _criar_equipe(client, headers, nivel, nome="Equipe X"):
    resposta = await client.post(
        "/api/v1/equipes", json={"nome": nome, "nivel": nivel}, headers=headers
    )
    return resposta.json()["id"]


async def test_criar_inscricao_retorna_201(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-insc-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2])
    equipe_id = await _criar_equipe(client, headers, nivel=1)

    resposta = await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["equipe_id"] == equipe_id
    assert corpo["modalidade_id"] == modalidade_id


async def test_criar_inscricao_com_nivel_incompativel_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-insc-2@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1])
    equipe_id = await _criar_equipe(client, headers, nivel=4)

    resposta = await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "NIVEL_EQUIPE_INCOMPATIVEL"


async def test_criar_inscricao_duplicada_retorna_409(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-insc-3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1])
    equipe_id = await _criar_equipe(client, headers, nivel=1)
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )

    resposta = await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "INSCRICAO_DUPLICADA"


async def test_listar_inscricoes_filtra_por_modalidade(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-insc-4@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_a = await _criar_modalidade(client, headers, evento_id, [1], nome="M-A")
    modalidade_b = await _criar_modalidade(client, headers, evento_id, [1], nome="M-B")
    equipe_id = await _criar_equipe(client, headers, nivel=1)
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_a},
        headers=headers,
    )

    resposta = await client.get(f"/api/v1/inscricoes?modalidade_id={modalidade_a}", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["modalidade_id"] == modalidade_a
    assert modalidade_b  # sanity: usada so para garantir isolamento do filtro


async def test_listar_inscricoes_aceita_size_ate_1000(client, db_session):
    # Mesmo teto de /equipes -- a tela de Equipes busca todas as inscricoes
    # de uma vez (sem paginar) pra montar "quais modalidades cada equipe
    # esta inscrita", e o teto antigo de 200 nao cobre um evento real.
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-insc-5@tjr.app")

    resposta = await client.get("/api/v1/inscricoes?size=1000", headers=headers)

    assert resposta.status_code == 200
    assert resposta.json()["size"] == 1000


async def test_listar_inscricoes_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-insc-6@tjr.app"
    )
    evento_id = await _criar_evento(client, headers_coord)
    modalidade_id = await _criar_modalidade(client, headers_coord, evento_id, [1])
    equipe_id = await _criar_equipe(client, headers_coord, nivel=1)
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers_coord,
    )
    headers_arbitro = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-insc@tjr.app")

    resposta = await client.get(
        f"/api/v1/inscricoes?modalidade_id={modalidade_id}", headers=headers_arbitro
    )

    assert resposta.status_code == 200


async def test_deletar_inscricao_remove_vinculo(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-insc-5@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1])
    equipe_id = await _criar_equipe(client, headers, nivel=1)
    criada = await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )
    inscricao_id = criada.json()["id"]

    resposta = await client.delete(f"/api/v1/inscricoes/{inscricao_id}", headers=headers)

    assert resposta.status_code == 204

    listagem = await client.get(
        f"/api/v1/inscricoes?modalidade_id={modalidade_id}", headers=headers
    )
    assert listagem.json()["total"] == 0
