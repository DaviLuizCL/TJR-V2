from app.models.usuario import Papel
from app.tests.api.v1.test_inscricoes_router import (
    _auth_header,
    _criar_evento,
    _criar_modalidade,
)
from app.tests.services.test_importacao_service import CABECALHO, _xlsx


async def test_checklist_retorna_secao_por_modalidade_e_itens_gerais(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-check-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    modalidade_id = await _criar_modalidade(client, headers, evento_id, [1, 2], nome="Dança")

    resposta = await client.get(
        "/api/v1/admin/checklist", params={"evento_id": evento_id}, headers=headers
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [m["modalidade_id"] for m in corpo["modalidades"]] == [modalidade_id]
    assert {i["codigo"] for i in corpo["gerais"]} == {"JUIZES", "NOTAS_PENDENTES"}


async def test_checklist_com_secretaria_e_permitido(client, db_session):
    coord = await _auth_header(client, db_session, Papel.COORDENADOR, "c-check-2@tjr.app")
    evento_id = await _criar_evento(client, coord)
    headers = await _auth_header(client, db_session, Papel.SECRETARIA, "s-check-2@tjr.app")

    resposta = await client.get(
        "/api/v1/admin/checklist", params={"evento_id": evento_id}, headers=headers
    )

    assert resposta.status_code == 200


async def test_checklist_com_arbitro_retorna_403(client, db_session):
    coord = await _auth_header(client, db_session, Papel.COORDENADOR, "c-check-3@tjr.app")
    evento_id = await _criar_evento(client, coord)
    headers = await _auth_header(client, db_session, Papel.ARBITRO, "a-check-3@tjr.app")

    resposta = await client.get(
        "/api/v1/admin/checklist", params={"evento_id": evento_id}, headers=headers
    )

    assert resposta.status_code == 403


async def _upload(client, headers, evento_id, conteudo, simular):
    return await client.post(
        "/api/v1/admin/importar-equipes",
        params={"evento_id": evento_id, "simular": simular},
        files={
            "arquivo": (
                "lista.xlsx",
                conteudo,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )


async def test_importar_equipes_em_simulacao_devolve_relatorio_sem_gravar(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-imp-1@tjr.app")
    evento_id = await _criar_evento(client, headers)
    await _criar_modalidade(client, headers, evento_id, [1, 2], nome="Sumô")
    planilha = _xlsx([CABECALHO, ["Sumô", "2", "E", "M", "Robotech"]])

    resposta = await _upload(client, headers, evento_id, planilha, simular=True)

    assert resposta.status_code == 200
    assert resposta.json()["equipes_novas"] == 1
    assert resposta.json()["simulacao"] is True
    equipes = await client.get("/api/v1/equipes", headers=headers)
    assert equipes.json()["total"] == 0


async def test_importar_equipes_de_verdade_grava(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-imp-2@tjr.app")
    evento_id = await _criar_evento(client, headers)
    await _criar_modalidade(client, headers, evento_id, [1, 2], nome="Sumô")
    planilha = _xlsx([CABECALHO, ["Sumô", "2", "E", "M", "Robotech"]])

    resposta = await _upload(client, headers, evento_id, planilha, simular=False)

    assert resposta.status_code == 200
    equipes = await client.get("/api/v1/equipes", headers=headers)
    assert [e["nome"] for e in equipes.json()["itens"]] == ["Robotech"]


async def test_importar_arquivo_invalido_retorna_422(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-imp-3@tjr.app")
    evento_id = await _criar_evento(client, headers)

    resposta = await _upload(client, headers, evento_id, b"nao sou planilha", simular=True)

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "PLANILHA_INVALIDA"


async def test_importar_equipes_com_secretaria_retorna_403(client, db_session):
    coord = await _auth_header(client, db_session, Papel.COORDENADOR, "c-imp-4@tjr.app")
    evento_id = await _criar_evento(client, coord)
    headers = await _auth_header(client, db_session, Papel.SECRETARIA, "s-imp-4@tjr.app")

    resposta = await _upload(client, headers, evento_id, _xlsx([CABECALHO]), simular=True)

    assert resposta.status_code == 403


async def test_backup_devolve_arquivo_para_download(client, db_session, monkeypatch):
    from app.api.v1 import admin as admin_router

    async def _backup_falso(database_url):
        return b"PGDMP-conteudo"

    monkeypatch.setattr(admin_router.backup_service, "gerar_backup", _backup_falso)
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "c-bkp-1@tjr.app")

    resposta = await client.get("/api/v1/admin/backup", headers=headers)

    assert resposta.status_code == 200
    assert resposta.content == b"PGDMP-conteudo"
    disposicao = resposta.headers["content-disposition"]
    assert disposicao.startswith('attachment; filename="tjr-backup-')
    assert disposicao.endswith('.dump"')


async def test_backup_com_secretaria_retorna_403(client, db_session):
    headers = await _auth_header(client, db_session, Papel.SECRETARIA, "s-bkp-2@tjr.app")

    resposta = await client.get("/api/v1/admin/backup", headers=headers)

    assert resposta.status_code == 403
