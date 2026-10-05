from datetime import date

from app.core.security import hash_senha
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
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


async def test_listar_equipes_aceita_size_maior_que_200(client, db_session):
    # Achado em teste de usabilidade com evento grande (489 equipes): o teto
    # antigo de size=200 fazia telas que buscam "todas as equipes de uma vez"
    # (chaveamento, horario, pontuar) mostrarem "?" no lugar do nome pra
    # qualquer equipe fora da primeira pagina.
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-8@tjr.app")

    resposta = await client.get("/api/v1/equipes?size=500", headers=headers)

    assert resposta.status_code == 200


async def test_listar_equipes_filtra_por_modalidade(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-equipes-7@tjr.app")
    resposta_a = await client.post(
        "/api/v1/equipes", json=_payload(nome="Inscrita em A"), headers=headers
    )
    resposta_b = await client.post(
        "/api/v1/equipes", json=_payload(nome="Inscrita em B"), headers=headers
    )
    equipe_a_id = resposta_a.json()["id"]
    equipe_b_id = resposta_b.json()["id"]

    evento = Evento(
        nome="Evento Filtro Modalidade",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    modalidade_a = Modalidade(
        evento_id=evento.id,
        nome="Modalidade A",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1, 2, 3, 4],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    modalidade_b = Modalidade(
        evento_id=evento.id,
        nome="Modalidade B",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1, 2, 3, 4],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add_all([modalidade_a, modalidade_b])
    await db_session.flush()

    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_a_id, "modalidade_id": str(modalidade_a.id)},
        headers=headers,
    )
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_b_id, "modalidade_id": str(modalidade_b.id)},
        headers=headers,
    )

    resposta = await client.get(f"/api/v1/equipes?modalidade_id={modalidade_a.id}", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["id"] == equipe_a_id


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


async def test_equipe_nasce_presente(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-equipes-pres1@tjr.app"
    )

    criada = await client.post("/api/v1/equipes", json=_payload(), headers=headers)

    assert criada.json()["presente"] is True


async def test_marcar_equipe_como_ausente(client, db_session):
    headers = await _auth_header(
        client, db_session, Papel.COORDENADOR, "coord-equipes-pres2@tjr.app"
    )
    criada = await client.post("/api/v1/equipes", json=_payload(), headers=headers)
    equipe_id = criada.json()["id"]

    resposta = await client.patch(
        f"/api/v1/equipes/{equipe_id}", json={"presente": False}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["presente"] is False
