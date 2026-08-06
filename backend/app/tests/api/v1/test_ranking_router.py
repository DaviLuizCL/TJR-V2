import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.core.security import hash_senha
from app.models.agendamento import Agendamento
from app.models.arena import Arena
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.ficha import publicar_ficha
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento


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


async def _criar_evento(db_session, nome="TJR 2026") -> Evento:
    evento = Evento(
        nome=nome,
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    return evento


async def _criar_modalidade_com_classificacao(
    db_session, evento, coordenador, *, nome="Resgate no Plano"
):
    modalidade = Modalidade(
        evento_id=evento.id,
        nome=nome,
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()

    ficha = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(ficha)
    await db_session.flush()
    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    arbitro = Usuario(
        nome="Arbitro",
        email=f"arbitro-{uuid.uuid4()}@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.ARBITRO,
    )
    db_session.add(arbitro)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    equipe = Equipe(nome="Equipe A", nivel=1)
    db_session.add(equipe)
    await db_session.flush()

    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )

    arena = Arena(modalidade_id=modalidade.id, nome="Arena 1", niveis_aplicaveis=None, ativo=True)
    db_session.add(arena)
    await db_session.flush()
    db_session.add(
        Agendamento(
            rodada_id=rodada.id,
            equipe_id=equipe.id,
            arena_id=arena.id,
            ordem_na_arena=0,
            horario_inicio=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        )
    )
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=3)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    return modalidade, equipe


async def test_liberar_ranking_via_patch_modalidade(client, db_session):
    headers = await _auth_header(client, db_session, Papel.COORDENADOR, "coord-ranking-1@tjr.app")
    coordenador_resp = await client.post(
        "/api/v1/eventos",
        json={"nome": "TJR", "ano": 2026, "data_inicio": "2026-03-10", "data_fim": "2026-03-12"},
        headers=headers,
    )
    evento_id = coordenador_resp.json()["id"]
    modalidade_resp = await client.post(
        "/api/v1/modalidades",
        json={
            "evento_id": evento_id,
            "nome": "Sumo",
            "tipo_disputa": "INDIVIDUAL",
            "niveis_aplicaveis": [1],
            "ficha_unica_entre_niveis": True,
            "qtd_rodadas": 1,
            "consolidacao": "SOMA_RODADAS",
        },
        headers=headers,
    )
    modalidade_id = modalidade_resp.json()["id"]
    assert modalidade_resp.json()["ranking_liberado"] is False

    resposta = await client.patch(
        f"/api/v1/modalidades/{modalidade_id}", json={"ranking_liberado": True}, headers=headers
    )

    assert resposta.status_code == 200
    assert resposta.json()["ranking_liberado"] is True


async def test_ranking_nao_liberado_retorna_403_sem_token(client, db_session):
    coordenador = await _criar_usuario(
        db_session, email="coord-ranking-2@tjr.app", papel=Papel.COORDENADOR
    )
    evento = await _criar_evento(db_session)
    modalidade, _equipe = await _criar_modalidade_com_classificacao(db_session, evento, coordenador)

    resposta = await client.get(f"/api/v1/ranking/modalidades/{modalidade.id}")

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "RANKING_NAO_LIBERADO"


async def test_ranking_liberado_retorna_200_sem_token(client, db_session):
    coordenador = await _criar_usuario(
        db_session, email="coord-ranking-3@tjr.app", papel=Papel.COORDENADOR
    )
    evento = await _criar_evento(db_session)
    modalidade, equipe = await _criar_modalidade_com_classificacao(db_session, evento, coordenador)
    modalidade.ranking_liberado = True
    await db_session.flush()

    resposta = await client.get(f"/api/v1/ranking/modalidades/{modalidade.id}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["itens"][0]["equipe_id"] == str(equipe.id)
    assert corpo["itens"][0]["equipe_nome"] == "Equipe A"
    assert corpo["itens"][0]["nota_final"] == 30
    assert corpo["itens"][0]["posicao"] == 1


async def test_staff_ve_ranking_mesmo_sem_liberar(client, db_session):
    coordenador = await _criar_usuario(
        db_session, email="coord-ranking-4@tjr.app", papel=Papel.COORDENADOR
    )
    evento = await _criar_evento(db_session)
    modalidade, _equipe = await _criar_modalidade_com_classificacao(db_session, evento, coordenador)
    headers_arbitro = await _auth_header(
        client, db_session, Papel.ARBITRO, "arbitro-ranking-ve@tjr.app"
    )

    resposta = await client.get(
        f"/api/v1/ranking/modalidades/{modalidade.id}", headers=headers_arbitro
    )

    assert resposta.status_code == 200


async def test_listagem_publica_so_traz_modalidades_liberadas(client, db_session):
    coordenador = await _criar_usuario(
        db_session, email="coord-ranking-5@tjr.app", papel=Papel.COORDENADOR
    )
    evento = await _criar_evento(db_session)
    liberada, _e1 = await _criar_modalidade_com_classificacao(
        db_session, evento, coordenador, nome="Liberada"
    )
    liberada.ranking_liberado = True
    nao_liberada, _e2 = await _criar_modalidade_com_classificacao(
        db_session, evento, coordenador, nome="Nao Liberada"
    )
    await db_session.flush()

    resposta = await client.get(f"/api/v1/ranking/modalidades?evento_id={evento.id}")

    assert resposta.status_code == 200
    ids = [item["id"] for item in resposta.json()]
    assert str(liberada.id) in ids
    assert str(nao_liberada.id) not in ids


async def test_ranking_mata_mata_traz_vitorias_derrotas_e_eliminado_por(client, db_session):
    coordenador = await _criar_usuario(
        db_session, email="coord-ranking-6@tjr.app", papel=Papel.COORDENADOR
    )
    evento = await _criar_evento(db_session)
    modalidade = Modalidade(
        evento_id=evento.id,
        nome="Sumo",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        niveis_aplicaveis=[2],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()

    equipe_a = Equipe(nome="Equipe A", nivel=2)
    equipe_b = Equipe(nome="Equipe B", nivel=2)
    db_session.add_all([equipe_a, equipe_b])
    await db_session.flush()
    for equipe in (equipe_a, equipe_b):
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )

    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            status=PartidaStatus.ENCERRADA,
        )
    )
    modalidade.ranking_liberado = True
    await db_session.flush()

    resposta = await client.get(f"/api/v1/ranking/modalidades/{modalidade.id}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo_disputa"] == "CONFRONTO"
    assert corpo["formato_chaveamento"] == "MATA_MATA"
    por_equipe = {item["equipe_id"]: item for item in corpo["itens"]}
    assert por_equipe[str(equipe_a.id)]["vitorias"] == 1
    assert por_equipe[str(equipe_a.id)]["eliminado_por_nome"] is None
    assert por_equipe[str(equipe_b.id)]["derrotas"] == 1
    assert por_equipe[str(equipe_b.id)]["eliminado_por_nome"] == "Equipe A"
    assert por_equipe[str(equipe_b.id)]["equipe_nivel"] == 2
