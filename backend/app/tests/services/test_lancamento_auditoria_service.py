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
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.lancamento import (
    confirmar_lancamento,
    criar_lancamento,
    listar_lancamentos_auditoria,
)


async def _criar_arbitro(
    db_session, nome="Arbitro Um", email="arbitro-auditoria@tjr.app"
) -> Usuario:
    usuario = Usuario(
        nome=nome, email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


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


async def _cenario(db_session, evento, *, nome_modalidade="Resgate no Plano", nivel_equipe=2):
    modalidade = Modalidade(
        evento_id=evento.id,
        nome=nome_modalidade,
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[nivel_equipe],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
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
    criterio_pontuacao = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    criterio_penalidade = Criterio(
        grupo_id=grupo.id,
        nome="Saiu da area",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("5"),
        ordem=2,
        ativo=True,
    )
    db_session.add_all([criterio_pontuacao, criterio_penalidade])
    await db_session.flush()

    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    equipe = Equipe(nome="Equipe Foguete", nivel=nivel_equipe)
    db_session.add(equipe)
    await db_session.flush()

    await _criar_agendamento(db_session, modalidade, rodada, equipe)

    return modalidade, ficha, rodada, equipe, criterio_pontuacao, criterio_penalidade


async def _criar_agendamento(db_session, modalidade, rodada, equipe) -> Agendamento:
    arena = Arena(modalidade_id=modalidade.id, nome="Arena 1", niveis_aplicaveis=None, ativo=True)
    db_session.add(arena)
    await db_session.flush()

    agendamento = Agendamento(
        rodada_id=rodada.id,
        equipe_id=equipe.id,
        arena_id=arena.id,
        ordem_na_arena=0,
        horario_inicio=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
    )
    db_session.add(agendamento)
    await db_session.flush()
    return agendamento


async def _lancar_confirmado(db_session, ficha, rodada, equipe, arbitro, itens_ocorrencias):
    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[
            ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)
            for criterio, ocorrencias in itens_ocorrencias.items()
        ],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    return await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)


async def test_listar_auditoria_traz_dados_enriquecidos_do_lancamento(db_session):
    evento = await _criar_evento(db_session)
    modalidade, ficha, rodada, equipe, criterio_p, criterio_pen = await _cenario(db_session, evento)
    arbitro = await _criar_arbitro(db_session, nome="Joana Arbitra")

    await _lancar_confirmado(
        db_session, ficha, rodada, equipe, arbitro, {criterio_p: 3, criterio_pen: 1}
    )

    resultados, total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, page=1, size=50
    )

    assert total == 1
    item = resultados[0]
    assert item.modalidade_nome == modalidade.nome
    assert item.nivel == equipe.nivel
    assert item.equipe_nome == "Equipe Foguete"
    assert item.rodada_numero == 1
    assert item.responsavel_nome == "Joana Arbitra"
    assert item.status.value == "CONFIRMADO"
    assert item.total == 25  # 30 de pontuacao - 5 de penalidade
    assert len(item.itens) == 2
    categorias = {i.criterio_snapshot["categoria"] for i in item.itens}
    assert categorias == {"PONTUACAO", "PENALIDADE"}


async def test_listar_auditoria_filtra_por_evento(db_session):
    evento_a = await _criar_evento(db_session, nome="Evento A")
    evento_b = await _criar_evento(db_session, nome="Evento B")
    modalidade_a, ficha_a, rodada_a, equipe_a, crit_a, crit_pen_a = await _cenario(
        db_session, evento_a, nome_modalidade="Modalidade A"
    )
    modalidade_b, ficha_b, rodada_b, equipe_b, crit_b, crit_pen_b = await _cenario(
        db_session, evento_b, nome_modalidade="Modalidade B"
    )
    arbitro = await _criar_arbitro(db_session, email="arbitro-filtro@tjr.app")

    await _lancar_confirmado(db_session, ficha_a, rodada_a, equipe_a, arbitro, {crit_a: 1})
    await _lancar_confirmado(db_session, ficha_b, rodada_b, equipe_b, arbitro, {crit_b: 1})

    resultados, total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento_a.id, page=1, size=50
    )

    assert total == 1
    assert resultados[0].modalidade_nome == "Modalidade A"


async def test_listar_auditoria_filtra_por_modalidade_dentro_do_mesmo_evento(db_session):
    evento = await _criar_evento(db_session)
    modalidade_a, ficha_a, rodada_a, equipe_a, crit_a, _pen_a = await _cenario(
        db_session, evento, nome_modalidade="Modalidade A"
    )
    modalidade_b, ficha_b, rodada_b, equipe_b, crit_b, _pen_b = await _cenario(
        db_session, evento, nome_modalidade="Modalidade B"
    )
    arbitro = await _criar_arbitro(db_session, email="arbitro-filtro-mod@tjr.app")

    await _lancar_confirmado(db_session, ficha_a, rodada_a, equipe_a, arbitro, {crit_a: 1})
    await _lancar_confirmado(db_session, ficha_b, rodada_b, equipe_b, arbitro, {crit_b: 1})

    resultados, total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, modalidade_id=modalidade_a.id, page=1, size=50
    )

    assert total == 1
    assert resultados[0].modalidade_nome == "Modalidade A"


async def test_listar_auditoria_ordena_por_mais_recente_primeiro(db_session):
    evento = await _criar_evento(db_session)
    modalidade, ficha, rodada, equipe, criterio_p, criterio_pen = await _cenario(db_session, evento)
    arbitro = await _criar_arbitro(db_session, email="arbitro-ordem@tjr.app")

    primeiro = await _lancar_confirmado(db_session, ficha, rodada, equipe, arbitro, {criterio_p: 1})
    segundo = await _lancar_confirmado(db_session, ficha, rodada, equipe, arbitro, {criterio_p: 2})

    resultados, _total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, page=1, size=50
    )

    assert [r.id for r in resultados] == [segundo.id, primeiro.id]


async def test_listar_auditoria_filtra_por_rodada(db_session):
    evento = await _criar_evento(db_session)
    modalidade, ficha, rodada_1, equipe, criterio_p, _pen = await _cenario(db_session, evento)
    rodada_2 = Rodada(
        modalidade_id=modalidade.id,
        numero=2,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada_2)
    await db_session.flush()
    await _criar_agendamento(db_session, modalidade, rodada_2, equipe)
    arbitro = await _criar_arbitro(db_session, email="arbitro-filtro-rodada@tjr.app")

    await _lancar_confirmado(db_session, ficha, rodada_1, equipe, arbitro, {criterio_p: 1})
    await _lancar_confirmado(db_session, ficha, rodada_2, equipe, arbitro, {criterio_p: 2})

    resultados, total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, rodada_id=rodada_1.id, page=1, size=50
    )

    assert total == 1
    assert resultados[0].rodada_numero == 1


async def test_listar_auditoria_filtra_por_equipe(db_session):
    evento = await _criar_evento(db_session)
    modalidade, ficha, rodada, equipe_a, criterio_p, _pen = await _cenario(db_session, evento)
    equipe_b = Equipe(nome="Equipe Trovao", nivel=2)
    db_session.add(equipe_b)
    await db_session.flush()
    await _criar_agendamento(db_session, modalidade, rodada, equipe_b)
    arbitro = await _criar_arbitro(db_session, email="arbitro-filtro-equipe@tjr.app")

    await _lancar_confirmado(db_session, ficha, rodada, equipe_a, arbitro, {criterio_p: 1})
    await _lancar_confirmado(db_session, ficha, rodada, equipe_b, arbitro, {criterio_p: 2})

    resultados, total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, equipe_id=equipe_b.id, page=1, size=50
    )

    assert total == 1
    assert resultados[0].equipe_nome == "Equipe Trovao"


async def test_listar_auditoria_filtra_por_equipe_sem_informar_evento(db_session):
    evento = await _criar_evento(db_session)
    modalidade, ficha, rodada, equipe, criterio_p, _pen = await _cenario(db_session, evento)
    arbitro = await _criar_arbitro(db_session, email="arbitro-sem-evento@tjr.app")

    await _lancar_confirmado(db_session, ficha, rodada, equipe, arbitro, {criterio_p: 1})

    resultados, total = await listar_lancamentos_auditoria(
        db_session, evento_id=None, equipe_id=equipe.id, page=1, size=50
    )

    assert total == 1
    assert resultados[0].equipe_nome == equipe.nome


async def test_listar_auditoria_pagina_resultados(db_session):
    evento = await _criar_evento(db_session)
    modalidade, ficha, rodada, equipe, criterio_p, criterio_pen = await _cenario(db_session, evento)
    arbitro = await _criar_arbitro(db_session, email="arbitro-pagina@tjr.app")

    for _ in range(3):
        await _lancar_confirmado(db_session, ficha, rodada, equipe, arbitro, {criterio_p: 1})

    pagina1, total = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, page=1, size=2
    )
    pagina2, _total2 = await listar_lancamentos_auditoria(
        db_session, evento_id=evento.id, page=2, size=2
    )

    assert total == 3
    assert len(pagina1) == 2
    assert len(pagina2) == 1
