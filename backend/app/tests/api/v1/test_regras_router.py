from app.models.usuario import Papel
from app.tests.api.v1.test_inscricoes_router import (
    _auth_header,
    _criar_evento,
    _criar_modalidade,
)

PDF = b"%PDF-1.4\n%conteudo de teste\n%%EOF"


async def _enviar(client, headers, modalidade_id, tipo, conteudo=PDF, nome="regra.pdf"):
    return await client.put(
        f"/api/v1/modalidades/{modalidade_id}/regras/{tipo}",
        files={"arquivo": (nome, conteudo, "application/pdf")},
        headers=headers,
    )


async def test_coordenador_envia_pdf_e_qualquer_um_baixa_sem_login(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2], nome="Dança")

    envio = await _enviar(client, headers, modalidade_id, "MANUAL", nome="Manual Dança.pdf")
    resposta = await client.get(f"/api/v1/publico/modalidades/{modalidade_id}/regras/MANUAL")

    assert envio.status_code == 200
    assert resposta.status_code == 200
    assert resposta.content == PDF
    assert resposta.headers["content-type"] == "application/pdf"
    # inline: abre no navegador do celular em vez de so baixar
    assert resposta.headers["content-disposition"].startswith("inline")


async def test_listagem_publica_de_regras_abre_sem_login(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r2@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2], nome="Dança")
    await _enviar(client, headers, modalidade_id, "CADERNO_ALUNO", nome="caderno.pdf")

    resposta = await client.get("/api/v1/publico/regras")

    assert resposta.status_code == 200
    (modalidade,) = resposta.json()
    assert modalidade["id"] == modalidade_id
    assert modalidade["nome"] == "Dança"
    assert [(r["tipo"], r["nome_arquivo"]) for r in modalidade["regras"]] == [
        ("CADERNO_ALUNO", "caderno.pdf")
    ]


async def test_pdf_que_nao_foi_enviado_retorna_404(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r3@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2])

    resposta = await client.get(f"/api/v1/publico/modalidades/{modalidade_id}/regras/MANUAL")

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "REGRA_NAO_ENCONTRADA"


async def test_arbitro_nao_pode_enviar_pdf(client, db_session):
    coord = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r4@tjr.app")
    evento_id = await _criar_evento(client, coord)
    modalidade_id = await _criar_modalidade(client, coord, evento_id, [1, 2])
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "a-regra-r4@tjr.app")

    resposta = await _enviar(client, headers, modalidade_id, "MANUAL")

    assert resposta.status_code == 403


async def test_sem_login_nao_pode_enviar_pdf(client, db_session):
    coord = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r5@tjr.app")
    evento_id = await _criar_evento(client, coord)
    modalidade_id = await _criar_modalidade(client, coord, evento_id, [1, 2])

    resposta = await _enviar(client, {}, modalidade_id, "MANUAL")

    assert resposta.status_code in (401, 403)


async def test_envio_de_arquivo_que_nao_e_pdf_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r6@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2])

    resposta = await _enviar(client, headers, modalidade_id, "MANUAL", conteudo=b"texto")

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "ARQUIVO_NAO_E_PDF"


async def test_coordenador_remove_pdf(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-regra-r7@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2])
    await _enviar(client, headers, modalidade_id, "MANUAL")

    remocao = await client.delete(
        f"/api/v1/modalidades/{modalidade_id}/regras/MANUAL", headers=headers
    )
    resposta = await client.get(f"/api/v1/publico/modalidades/{modalidade_id}/regras/MANUAL")

    assert remocao.status_code == 204
    assert resposta.status_code == 404
