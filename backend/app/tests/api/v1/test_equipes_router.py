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


def _payload(**overrides):
    base = {"nome": "Equipe Robotica X", "nivel": 3}
    base.update(overrides)
    return base


async def test_criar_equipe_com_coordenador_retorna_201(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-1@tjr.app")

    resposta = await client.post("/api/v1/equipes", json=_payload(), headers=headers)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Equipe Robotica X"
    assert corpo["ativo"] is True


async def test_criar_equipe_com_papel_arbitro_retorna_403(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arbitro-equipes@tjr.app")

    resposta = await client.post("/api/v1/equipes", json=_payload(), headers=headers)

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "PAPEL_NAO_AUTORIZADO"


async def test_criar_equipe_com_nivel_invalido_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-2@tjr.app")

    resposta = await client.post("/api/v1/equipes", json=_payload(nivel=9), headers=headers)

    assert resposta.status_code == 422


async def test_listar_equipes_filtra_por_nivel(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-3@tjr.app")
    await client.post("/api/v1/equipes", json=_payload(nome="E1", nivel=1), headers=headers)
    await client.post("/api/v1/equipes", json=_payload(nome="E2", nivel=2), headers=headers)

    resposta = await client.get("/api/v1/equipes?nivel=2", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["nome"] == "E2"


async def test_listar_equipes_com_papel_arbitro_retorna_200(client, db_session):
    headers_coord = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-equipes-6@tjr.app"
    )
    await client.post("/api/v1/equipes", json=_payload(), headers=headers_coord)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-equipes-2@tjr.app"
    )

    resposta = await client.get("/api/v1/equipes", headers=headers_arbitro)

    assert resposta.status_code == 200


async def test_obter_equipe_inexistente_retorna_404(client, db_session):
    import uuid

    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-4@tjr.app")

    resposta = await client.get(f"/api/v1/equipes/{uuid.uuid4()}", headers=headers)

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "EQUIPE_NAO_ENCONTRADA"


async def test_atualizar_equipe_desativa(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-5@tjr.app")
    criada = await client.post("/api/v1/equipes", json=_payload(), headers=headers)
    equipe_id = criada.json()["id"]

    resposta = await client.patch(
        f"/api/v1/equipes/{equipe_id}", json={"ativo": False}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["ativo"] is False
