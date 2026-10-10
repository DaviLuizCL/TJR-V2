from app.models.usuario import Papel
from app.tests.api.v1.test_inscricoes_router import (
    _auth_header,
    _criar_equipe,
    _criar_evento,
    _criar_modalidade,
)


async def _preparar(client, db_session, email):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, email)
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2])
    equipe_ids = []
    for nome in ("A", "B", "C"):
        equipe_id = await _criar_equipe(client, headers, nivel=1, nome=nome)
        await client.post(
            "/api/v1/inscricoes",
            json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
            headers=headers,
        )
        equipe_ids.append(equipe_id)
    return headers, modalidade_id, equipe_ids


async def _ordem(client, headers, modalidade_id):
    resposta = await client.get(
        "/api/v1/inscricoes", params={"modalidade_id": modalidade_id}, headers=headers
    )
    return {i["equipe_id"]: i["ordem_apresentacao"] for i in resposta.json()["itens"]}


async def test_sortear_ordem_preenche_ordem_apresentacao_nas_inscricoes(client, db_session):
    headers, modalidade_id, equipe_ids = await _preparar(client, db_session, "c-ordem-1@tjr.app")

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/ordem-apresentacao/sortear",
        json={"nivel": 1},
        headers=headers,
    )

    assert resposta.status_code == 204
    ordem = await _ordem(client, headers, modalidade_id)
    assert sorted(ordem[e] for e in equipe_ids) == [1, 2, 3]


async def test_definir_ordem_grava_sequencia_manual(client, db_session):
    headers, modalidade_id, (a, b, c) = await _preparar(client, db_session, "c-ordem-2@tjr.app")

    resposta = await client.put(
        f"/api/v1/modalidades/{modalidade_id}/ordem-apresentacao",
        json={"nivel": 1, "equipe_ids": [b, c, a]},
        headers=headers,
    )

    assert resposta.status_code == 204
    ordem = await _ordem(client, headers, modalidade_id)
    assert (ordem[b], ordem[c], ordem[a]) == (1, 2, 3)


async def test_definir_ordem_incompleta_retorna_422(client, db_session):
    headers, modalidade_id, (a, _, _) = await _preparar(client, db_session, "c-ordem-3@tjr.app")

    resposta = await client.put(
        f"/api/v1/modalidades/{modalidade_id}/ordem-apresentacao",
        json={"nivel": 1, "equipe_ids": [a]},
        headers=headers,
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "ORDEM_INCOMPLETA"


async def test_arbitro_nao_pode_sortear_ordem(client, db_session):
    _, modalidade_id, _ = await _preparar(client, db_session, "c-ordem-4@tjr.app")
    headers_arbitro = await _auth_header(client, db_session, Papel.ARBITRO, "arb-ordem@tjr.app")

    resposta = await client.post(
        f"/api/v1/modalidades/{modalidade_id}/ordem-apresentacao/sortear",
        json={"nivel": 1},
        headers=headers_arbitro,
    )

    assert resposta.status_code == 403


async def test_baixar_pdf_da_sequencia_devolve_pdf_para_download(client, db_session):
    _, modalidade_id, _ = await _preparar(client, db_session, "c-ordem-5@tjr.app")
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "arb-ordem-5@tjr.app")

    resposta = await client.get(
        f"/api/v1/modalidades/{modalidade_id}/sequencia-competicao.pdf", headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")
    assert "attachment" in resposta.headers["content-disposition"]


async def test_baixar_pdf_da_sequencia_sem_login_retorna_401(client, db_session):
    _, modalidade_id, _ = await _preparar(client, db_session, "c-ordem-6@tjr.app")

    resposta = await client.get(f"/api/v1/modalidades/{modalidade_id}/sequencia-competicao.pdf")

    assert resposta.status_code == 401
