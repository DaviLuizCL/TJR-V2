import uuid

from app.models.usuario import Papel
from app.tests.api.v1.test_inscricoes_router import (
    _auth_header,
    _criar_equipe,
    _criar_evento,
    _criar_modalidade,
)


async def test_sequencia_publica_abre_sem_login(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-pub-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2], nome="Dança")
    equipe_id = await _criar_equipe(client, headers, nivel=1, nome="Equipe A")
    await client.post(
        "/api/v1/inscricoes",
        json={"equipe_id": equipe_id, "modalidade_id": modalidade_id},
        headers=headers,
    )

    resposta = await client.get("/api/v1/publico/sequencia")

    assert resposta.status_code == 200
    (modalidade,) = resposta.json()
    assert modalidade["nome"] == "Dança"
    assert modalidade["niveis"][0]["equipes"] == [
        {
            "nome": "Equipe A",
            "posicao": 1,
            "presente": True,
            "rodadas_competidas": [],
            "proxima": False,
            "equipes_na_frente": None,
        }
    ]


async def test_sequencia_publica_sem_evento_cadastrado_retorna_404(client):
    resposta = await client.get("/api/v1/publico/sequencia")

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "EVENTO_NAO_ENCONTRADO"


async def test_endereco_antigo_com_id_do_evento_nao_existe_mais(client):
    resposta = await client.get(f"/api/v1/publico/eventos/{uuid.uuid4()}/sequencia")

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] != "EVENTO_NAO_ENCONTRADO"
