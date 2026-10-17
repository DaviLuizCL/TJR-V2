from app.models.usuario import Papel
from app.tests.api.v1.test_inscricoes_router import _auth_header

_PEDIDO = {"nome": "Juiz Novo", "email": "Juiz.Novo@tjr.app", "senha": "segredo1"}


async def _pedir(client, pedido=None):
    return await client.post("/api/v1/solicitacoes-acesso", json=pedido or _PEDIDO)


async def _coordenador(client, db_session):
    return await _auth_header(client, db_session, Papel.COORDENADOR, "coord-solic-r@tjr.app")


async def test_juiz_pede_acesso_sem_login(client):
    resposta = await _pedir(client)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Juiz Novo"
    assert corpo["email"] == "juiz.novo@tjr.app"
    assert corpo["status"] == "PENDENTE"
    assert "senha" not in corpo and "senha_hash" not in corpo


async def test_pedido_com_senha_curta_e_recusado(client):
    resposta = await _pedir(client, {**_PEDIDO, "senha": "123"})

    assert resposta.status_code == 422


async def test_segundo_pedido_do_mesmo_email_retorna_409(client):
    await _pedir(client)

    resposta = await _pedir(client)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "SOLICITACAO_JA_PENDENTE"


async def test_coordenador_lista_os_pedidos_pendentes(client, db_session):
    headers = await _coordenador(client, db_session)
    await _pedir(client)

    resposta = await client.get("/api/v1/solicitacoes-acesso", headers=headers)

    assert resposta.status_code == 200
    (pedido,) = resposta.json()
    assert pedido["email"] == "juiz.novo@tjr.app"
    assert "senha_hash" not in pedido


async def test_juiz_nao_ve_os_pedidos(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "juiz-solic-r@tjr.app")

    resposta = await client.get("/api/v1/solicitacoes-acesso", headers=headers)

    assert resposta.status_code == 403


async def test_sem_login_nao_ve_os_pedidos(client):
    resposta = await client.get("/api/v1/solicitacoes-acesso")

    assert resposta.status_code == 401


async def test_juiz_nao_aprova_pedido(client, db_session):
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "juiz-solic-r@tjr.app")
    pedido = (await _pedir(client)).json()

    resposta = await client.post(
        f"/api/v1/solicitacoes-acesso/{pedido['id']}/aprovar", headers=headers
    )

    assert resposta.status_code == 403


async def test_aprovado_o_juiz_entra_com_a_senha_que_escolheu(client, db_session):
    headers = await _coordenador(client, db_session)
    pedido = (await _pedir(client)).json()

    aprovacao = await client.post(
        f"/api/v1/solicitacoes-acesso/{pedido['id']}/aprovar", headers=headers
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "juiz.novo@tjr.app", "senha": "segredo1"}
    )

    assert aprovacao.status_code == 200
    assert aprovacao.json()["papel"] == "ARBITRO"
    assert login.status_code == 200


async def test_recusado_some_da_lista_e_nao_entra(client, db_session):
    headers = await _coordenador(client, db_session)
    pedido = (await _pedir(client)).json()

    recusa = await client.post(
        f"/api/v1/solicitacoes-acesso/{pedido['id']}/recusar", headers=headers
    )
    lista = await client.get("/api/v1/solicitacoes-acesso", headers=headers)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "juiz.novo@tjr.app", "senha": "segredo1"}
    )

    assert recusa.status_code == 204
    assert lista.json() == []
    assert login.status_code == 401
    assert login.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_login_de_quem_ainda_espera_aprovacao_avisa_que_esta_pendente(client):
    await _pedir(client)

    resposta = await client.post(
        "/api/v1/auth/login", json={"email": "juiz.novo@tjr.app", "senha": "segredo1"}
    )

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "ACESSO_AGUARDANDO_APROVACAO"


async def test_login_pendente_com_senha_errada_continua_credenciais_invalidas(client):
    await _pedir(client)

    resposta = await client.post(
        "/api/v1/auth/login", json={"email": "juiz.novo@tjr.app", "senha": "errada!"}
    )

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_coordenador_pode_aprovar_como_coordenador(client, db_session):
    headers = await _coordenador(client, db_session)
    pedido = (await _pedir(client)).json()

    resposta = await client.post(
        f"/api/v1/solicitacoes-acesso/{pedido['id']}/aprovar",
        json={"papel": "COORDENADOR"},
        headers=headers,
    )

    assert resposta.status_code == 200
    assert resposta.json()["papel"] == "COORDENADOR"


async def test_aprovar_so_aceita_juiz_ou_coordenador(client, db_session):
    headers = await _coordenador(client, db_session)
    pedido = (await _pedir(client)).json()

    resposta = await client.post(
        f"/api/v1/solicitacoes-acesso/{pedido['id']}/aprovar",
        json={"papel": "PUBLICO"},
        headers=headers,
    )

    assert resposta.status_code == 422
