import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.lancamento import Lancamento
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import (
    Consolidacao,
    DecisaoPartida,
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
from app.schemas.modalidade import ModalidadeUpdate
from app.services.chaveamento import (
    avancar_se_rodada_completa,
    gerar_chaveamento_confronto,
    gerar_chaveamento_inicial,
    registrar_resultado_lancamento,
    resetar_chaveamento,
)
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento
from app.services.modalidade import atualizar_modalidade
from app.services.rodada import gerar_rodadas


async def _criar_coordenador(db_session, email="coord-chaveamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_arbitro(db_session, email="arbitro-chaveamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Arbitro", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade_confronto(
    db_session,
    *,
    nome="Combate",
    evento_id=None,
    formato=FormatoChaveamento.MATA_MATA,
    niveis_aplicaveis=None,
    tentativas_por_rodada=1,
    decisao_partida=DecisaoPartida.COMBATES_VENCIDOS,
) -> Modalidade:
    if evento_id is None:
        evento = Evento(
            nome="TJR 2026",
            ano=2026,
            data_inicio=date(2026, 3, 10),
            data_fim=date(2026, 3, 12),
            status=EventoStatus.RASCUNHO,
        )
        db_session.add(evento)
        await db_session.flush()
        evento_id = evento.id

    modalidade = Modalidade(
        evento_id=evento_id,
        nome=nome,
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=formato,
        niveis_aplicaveis=niveis_aplicaveis or [1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=5,
        tentativas_por_rodada=tentativas_por_rodada,
        consolidacao=Consolidacao.SOMA_RODADAS,
        decisao_partida=decisao_partida,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever_equipes(db_session, modalidade, coordenador, qtd, nivel=1) -> list[Equipe]:
    equipes = []
    for i in range(qtd):
        equipe = Equipe(nome=f"Equipe {i + 1}", nivel=nivel)
        db_session.add(equipe)
        await db_session.flush()
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )
        equipes.append(equipe)
    return equipes


async def _inscrever_equipes_por_nivel(db_session, modalidade, coordenador, niveis) -> list[Equipe]:
    """Cria uma equipe pra cada nivel da lista informada (ex.: [1, 1, 2, 2] cria
    2 equipes de nivel 1 e 2 de nivel 2), todas inscritas na mesma modalidade.
    """
    equipes = []
    for i, nivel in enumerate(niveis):
        equipe = Equipe(nome=f"Equipe {i + 1} Nivel {nivel}", nivel=nivel)
        db_session.add(equipe)
        await db_session.flush()
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )
        equipes.append(equipe)
    return equipes


async def _criar_ficha_com_criterio(db_session, modalidade, coordenador) -> tuple[Ficha, Criterio]:
    ficha = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(ficha)
    await db_session.flush()
    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Ataque",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()
    from app.services.ficha import publicar_ficha

    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    return ficha, criterio


async def _lancar_e_confirmar(
    db_session, ficha, rodada, equipe, criterio, partida, arbitro, ocorrencias, tentativa=1
):
    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=tentativa,
        equipe_id=equipe.id,
        partida_id=partida.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    return await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)


# ---------- gerar_chaveamento_inicial ----------


async def test_gerar_chaveamento_recusa_modalidade_individual(db_session):
    coordenador = await _criar_coordenador(db_session, "c1@tjr.app")
    evento = Evento(
        nome="E",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    modalidade = Modalidade(
        evento_id=evento.id,
        nome="Individual",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "MODALIDADE_NAO_E_CONFRONTO"


async def test_gerar_chaveamento_recusa_formato_todos_contra_todos(db_session):
    coordenador = await _criar_coordenador(db_session, "c2@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    await _inscrever_equipes(db_session, modalidade, coordenador, 4)

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "FORMATO_CHAVEAMENTO_INVALIDO_PARA_GERAR"


async def test_gerar_chaveamento_recusa_menos_de_duas_equipes(db_session):
    coordenador = await _criar_coordenador(db_session, "c3@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    await _inscrever_equipes(db_session, modalidade, coordenador, 1)

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "EQUIPES_INSUFICIENTES"


async def test_gerar_chaveamento_recusa_se_ja_iniciado(db_session):
    coordenador = await _criar_coordenador(db_session, "c4@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "CHAVEAMENTO_JA_INICIADO"


async def test_gerar_chaveamento_com_numero_par_nao_gera_bye(db_session):
    coordenador = await _criar_coordenador(db_session, "c5@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    equipe_ids = {e.id for e in equipes}

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    assert rodada.numero == 1
    from app.services.partida import listar_partidas_por_rodada

    partidas = await listar_partidas_por_rodada(db_session, rodada.id)
    assert len(partidas) == 2
    todos_participantes = set()
    for p in partidas:
        assert p.equipe_b_id is not None
        assert p.status == PartidaStatus.AGENDADA
        assert p.vencedor_id is None
        todos_participantes.add(p.equipe_a_id)
        todos_participantes.add(p.equipe_b_id)
    assert todos_participantes == equipe_ids


async def test_gerar_chaveamento_com_numero_impar_da_bye_automatico(db_session):
    coordenador = await _criar_coordenador(db_session, "c6@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    await _inscrever_equipes(db_session, modalidade, coordenador, 3)

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    from app.services.partida import listar_partidas_por_rodada

    partidas = await listar_partidas_por_rodada(db_session, rodada.id)
    assert len(partidas) == 2
    byes = [p for p in partidas if p.equipe_b_id is None]
    assert len(byes) == 1
    assert byes[0].status == PartidaStatus.ENCERRADA
    assert byes[0].vencedor_id == byes[0].equipe_a_id


# ---------- registrar_resultado_lancamento + avancar_se_rodada_completa (integracao) ----------


async def test_confirmar_os_dois_lancamentos_fecha_a_partida_com_vencedor(db_session):
    coordenador = await _criar_coordenador(db_session, "c8@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a8@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 1)
    partida_meio = await db_session.get(Partida, partida.id)
    assert partida_meio.status == PartidaStatus.AGENDADA  # so uma equipe lancou ainda

    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 3)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_b.id


async def test_empate_nao_fecha_a_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "c9@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a9@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 2)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 2)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.AGENDADA
    assert partida_final.vencedor_id is None


async def test_mata_mata_avanca_pareando_vencedores_em_ordem(db_session):
    coordenador = await _criar_coordenador(db_session, "c10@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a10@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada1 = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partidas1 = await listar_partidas_por_rodada(db_session, rodada1.id)
    assert len(partidas1) == 2

    vencedores_esperados = []
    for partida in partidas1:
        equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
        equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_a, criterio, partida, arbitro, 1
        )
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_b, criterio, partida, arbitro, 5
        )
        vencedores_esperados.append(equipe_b.id)

    # O avanco ja aconteceu sozinho, disparado de dentro de _lancar_e_confirmar
    # (confirmar_lancamento -> registrar_resultado_lancamento) assim que a
    # ultima partida da rodada fechou - sem clique nem chamada manual nenhuma,
    # igual ao caminho real do arbitro. Chamar avancar_se_rodada_completa de
    # novo aqui e um no-op idempotente (nao ha mais nada pra avancar).
    rodada2 = await db_session.scalar(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id, Rodada.numero == 2)
    )
    assert rodada2 is not None
    partidas2 = await listar_partidas_por_rodada(db_session, rodada2.id)
    assert len(partidas2) == 1
    assert {partidas2[0].equipe_a_id, partidas2[0].equipe_b_id} == set(vencedores_esperados)

    assert (
        await avancar_se_rodada_completa(db_session, rodada1.id, usuario_id=coordenador.id) is None
    )


async def test_mata_mata_final_nao_gera_proxima_rodada(db_session):
    coordenador = await _criar_coordenador(db_session, "c11@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a11@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada1 = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada1.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)
    await _lancar_e_confirmar(db_session, ficha, rodada1, equipe_a, criterio, partida, arbitro, 1)
    await _lancar_e_confirmar(db_session, ficha, rodada1, equipe_b, criterio, partida, arbitro, 5)

    proxima = await avancar_se_rodada_completa(db_session, rodada1.id, usuario_id=coordenador.id)

    assert proxima is None


async def test_todos_contra_todos_com_vencedor_fecha_partida_sem_avancar_rodada(db_session):
    coordenador = await _criar_coordenador(db_session, "c16@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a16@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 1)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[1], criterio, partida, arbitro, 3)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipes[1].id

    resultado = await db_session.execute(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id)
    )
    assert len(resultado.scalars().all()) == 1


async def test_todos_contra_todos_com_empate_marca_partida_empatada(db_session):
    coordenador = await _criar_coordenador(db_session, "c17@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a17@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 2)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[1], criterio, partida, arbitro, 2)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.EMPATADA
    assert partida_final.vencedor_id is None


async def test_registrar_resultado_usa_formato_da_partida_nao_da_modalidade(db_session):
    # Cenario alvo do chaveamento por nivel: modalidade.formato_chaveamento
    # fica None (decisao automatica por nivel, ver gerar_chaveamento_confronto),
    # entao quem decide o comportamento de uma partida especifica e o
    # formato_chaveamento gravado nela mesma, nao mais o campo da modalidade.
    coordenador = await _criar_coordenador(db_session, "c17b@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a17b@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 2)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[1], criterio, partida, arbitro, 2)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.EMPATADA


async def test_registrar_resultado_ignora_lancamento_sem_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "c14@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a14@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipes[0].id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=1)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    confirmado = await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    # nao deve levantar erro nem tentar fechar partida nenhuma (lancamento.partida_id e None)
    await registrar_resultado_lancamento(db_session, confirmado, usuario_id=arbitro.id)


# ---------- separacao do chaveamento por nivel ----------


async def test_gerar_chaveamento_separa_por_nivel(db_session):
    coordenador = await _criar_coordenador(db_session, "c18@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])
    equipes = await _inscrever_equipes_por_nivel(db_session, modalidade, coordenador, [1, 1, 2, 2])
    nivel_por_equipe = {e.id: e.nivel for e in equipes}

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    from app.services.partida import listar_partidas_por_rodada

    partidas = await listar_partidas_por_rodada(db_session, rodada.id)
    assert len(partidas) == 2
    for partida in partidas:
        nivel_a = nivel_por_equipe[partida.equipe_a_id]
        nivel_b = nivel_por_equipe[partida.equipe_b_id]
        assert nivel_a == nivel_b
        assert partida.nivel == nivel_a


async def test_gerar_chaveamento_nivel_com_uma_equipe_nao_gera_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "c19@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])
    equipes = await _inscrever_equipes_por_nivel(db_session, modalidade, coordenador, [1, 1, 2])
    equipe_solitaria = next(e for e in equipes if e.nivel == 2)

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    from app.services.partida import listar_partidas_por_rodada

    partidas = await listar_partidas_por_rodada(db_session, rodada.id)
    assert len(partidas) == 1
    participantes = {partidas[0].equipe_a_id, partidas[0].equipe_b_id}
    assert equipe_solitaria.id not in participantes


async def test_gerar_chaveamento_confronto_decide_formato_por_nivel_pela_contagem(db_session):
    # Regra real (LISTA 2026): dentro da MESMA modalidade, nivel com <=5
    # equipes vira todos-contra-todos, nivel com 6+ vira mata-mata -
    # modalidade.formato_chaveamento=None e o sinal de "decida sozinho".
    coordenador = await _criar_coordenador(db_session, "c-auto1@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=None, niveis_aplicaveis=[1, 2]
    )
    await _inscrever_equipes_por_nivel(
        db_session, modalidade, coordenador, [1, 1, 1, 2, 2, 2, 2, 2, 2]
    )

    from app.services.partida import listar_partidas_por_rodada

    rodadas = await gerar_chaveamento_confronto(
        db_session, modalidade.id, usuario_id=coordenador.id
    )

    todas_partidas = []
    for rodada in rodadas:
        todas_partidas.extend(await listar_partidas_por_rodada(db_session, rodada.id))

    partidas_nivel_1 = [p for p in todas_partidas if p.nivel == 1]
    partidas_nivel_2 = [p for p in todas_partidas if p.nivel == 2]

    assert partidas_nivel_1
    assert all(
        p.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS for p in partidas_nivel_1
    )
    assert partidas_nivel_2
    assert all(p.formato_chaveamento == FormatoChaveamento.MATA_MATA for p in partidas_nivel_2)
    # nivel 1 (returno com 3 equipes) precisa de mais de 1 rodada.
    assert len({p.rodada_id for p in partidas_nivel_1}) > 1
    # nivel 2 (bracket) so gera a rodada de saida, o resto e dinamico.
    assert len({p.rodada_id for p in partidas_nivel_2}) == 1


async def test_gerar_chaveamento_confronto_override_manual_ignora_contagem(db_session):
    coordenador = await _criar_coordenador(db_session, "c-auto2@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.MATA_MATA, niveis_aplicaveis=[1]
    )
    # 3 equipes cairia em todos-contra-todos pela regra automatica, mas o
    # campo explicito da modalidade forca mata-mata mesmo assim.
    await _inscrever_equipes_por_nivel(db_session, modalidade, coordenador, [1, 1, 1])

    from app.services.partida import listar_partidas_por_rodada

    rodadas = await gerar_chaveamento_confronto(
        db_session, modalidade.id, usuario_id=coordenador.id
    )
    partidas = await listar_partidas_por_rodada(db_session, rodadas[0].id)

    assert partidas
    assert all(p.formato_chaveamento == FormatoChaveamento.MATA_MATA for p in partidas)


async def test_gerar_chaveamento_confronto_recusa_modalidade_individual(db_session):
    coordenador = await _criar_coordenador(db_session, "c-auto3@tjr.app")
    evento = Evento(
        nome="E-auto",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    modalidade = Modalidade(
        evento_id=evento.id,
        nome="Individual",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_confronto(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "MODALIDADE_NAO_E_CONFRONTO"


async def test_gerar_chaveamento_confronto_recusa_equipes_insuficientes(db_session):
    coordenador = await _criar_coordenador(db_session, "c-auto4@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    await _inscrever_equipes(db_session, modalidade, coordenador, 1)

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_confronto(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "EQUIPES_INSUFICIENTES"


async def test_gerar_chaveamento_confronto_recusa_se_ja_iniciado(db_session):
    coordenador = await _criar_coordenador(db_session, "c-auto5@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    await _inscrever_equipes(db_session, modalidade, coordenador, 3)
    await gerar_chaveamento_confronto(db_session, modalidade.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_confronto(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "CHAVEAMENTO_JA_INICIADO"


async def test_gerar_chaveamento_confronto_recusa_iniciar_sumo_rc_com_sumo_em_andamento(
    db_session,
):
    # Sumo RC 1,5kg e Sumo 1,5kg tradicional competem com o mesmo robo
    # possivel - as duas nao podem estar "abertas" (com combate pendente) ao
    # mesmo tempo, senao um arbitro pode chamar a mesma equipe pras duas
    # modalidades no mesmo instante. Sem agenda de horario pro confronto,
    # a trava e travar o INICIO da segunda ate a primeira fechar de vez.
    coordenador = await _criar_coordenador(db_session, "c-conflito-sumo@tjr.app")
    sumo = await _criar_modalidade_confronto(db_session, nome="Sumô", formato=None)
    sumo_rc = await _criar_modalidade_confronto(
        db_session, nome="Sumô RC 1,5 kg", evento_id=sumo.evento_id, formato=None
    )
    await _inscrever_equipes(db_session, sumo, coordenador, 3)
    await _inscrever_equipes(db_session, sumo_rc, coordenador, 3)

    await gerar_chaveamento_confronto(db_session, sumo.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await gerar_chaveamento_confronto(db_session, sumo_rc.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "MODALIDADE_CONFLITANTE_EM_ANDAMENTO"


async def test_gerar_chaveamento_confronto_permite_sumo_rc_depois_do_sumo_encerrado(db_session):
    coordenador = await _criar_coordenador(db_session, "c-conflito-sumo2@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a-conflito-sumo2@tjr.app")
    sumo = await _criar_modalidade_confronto(
        db_session, nome="Sumô", formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    sumo_rc = await _criar_modalidade_confronto(
        db_session, nome="Sumô RC 1,5 kg", evento_id=sumo.evento_id, formato=None
    )
    equipes = await _inscrever_equipes(db_session, sumo, coordenador, 2)
    await _inscrever_equipes(db_session, sumo_rc, coordenador, 3)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, sumo, coordenador)

    rodadas = await gerar_chaveamento_confronto(db_session, sumo.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    [partida] = await listar_partidas_por_rodada(db_session, rodadas[0].id)
    await _lancar_e_confirmar(
        db_session, ficha, rodadas[0], equipes[0], criterio, partida, arbitro, 4
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodadas[0], equipes[1], criterio, partida, arbitro, 2
    )

    # Sumo fechou (unica partida ENCERRADA) -- Sumo RC agora pode iniciar.
    rodadas_rc = await gerar_chaveamento_confronto(
        db_session, sumo_rc.id, usuario_id=coordenador.id
    )
    assert rodadas_rc


async def test_mata_mata_avanca_niveis_de_tamanhos_diferentes_independente(db_session):
    coordenador = await _criar_coordenador(db_session, "c20@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a20@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])
    equipes = await _inscrever_equipes_por_nivel(
        db_session, modalidade, coordenador, [1, 1, 1, 1, 2, 2]
    )
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada1 = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    from app.services.partida import listar_partidas_por_rodada

    partidas1 = await listar_partidas_por_rodada(db_session, rodada1.id)
    assert len(partidas1) == 3  # 2 do nivel 1 (4 equipes) + 1 do nivel 2 (2 equipes)

    for partida in partidas1:
        equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
        equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_a, criterio, partida, arbitro, 1
        )
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_b, criterio, partida, arbitro, 5
        )

    # O avanco do nivel 1 ja aconteceu sozinho, no meio do loop acima, assim
    # que a segunda partida desse nivel fechou - sem esperar o nivel 2
    # terminar (que so tem 1 partida = ja e a final dele, sem rodada extra).
    rodada2 = await db_session.scalar(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id, Rodada.numero == 2)
    )
    assert rodada2 is not None
    partidas2 = await listar_partidas_por_rodada(db_session, rodada2.id)
    # nivel 2 (2 equipes) ja tem campeao definido na rodada 1; so o nivel 1
    # (4 equipes) precisa de mais uma rodada pra decidir o campeao.
    assert len(partidas2) == 1
    assert partidas2[0].nivel == 1

    assert (
        await avancar_se_rodada_completa(db_session, rodada1.id, usuario_id=coordenador.id) is None
    )


async def test_mata_mata_gera_proxima_rodada_de_um_nivel_sem_esperar_outro_nivel_fechar(
    db_session,
):
    """Bug real relatado pelo usuario: pontuou todas as partidas do nivel 1
    (Sumo) e a final desse nivel nao apareceu, porque o nivel 2 ainda estava
    em aberto. O avanco e automatico (disparado de dentro de
    confirmar_lancamento, via registrar_resultado_lancamento), sem nenhuma
    chamada manual a avancar_se_rodada_completa aqui - exatamente o caminho
    real do arbitro em campo.
    """
    coordenador = await _criar_coordenador(db_session, "c30@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a30@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])
    equipes = await _inscrever_equipes_por_nivel(
        db_session, modalidade, coordenador, [1, 1, 1, 1, 2, 2, 2, 2]
    )
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada1 = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    from app.services.partida import listar_partidas_por_rodada

    partidas1 = await listar_partidas_por_rodada(db_session, rodada1.id)
    partidas_nivel_1 = [p for p in partidas1 if p.nivel == 1]
    partidas_nivel_2 = [p for p in partidas1 if p.nivel == 2]
    assert len(partidas_nivel_1) == 2
    assert len(partidas_nivel_2) == 2

    # So fecha as partidas do nivel 1. O nivel 2 fica em aberto de proposito
    # (nenhum lancamento), como no caso real relatado.
    for partida in partidas_nivel_1:
        equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
        equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_a, criterio, partida, arbitro, 1
        )
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_b, criterio, partida, arbitro, 5
        )

    rodada2 = await db_session.scalar(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id, Rodada.numero == 2)
    )
    assert rodada2 is not None, "nivel 1 terminou mas a proxima rodada dele nao foi gerada"

    partidas2 = await listar_partidas_por_rodada(db_session, rodada2.id)
    assert len(partidas2) == 1
    assert partidas2[0].nivel == 1


# ---------- partida em melhor-de-3 (3 tentativas por partida) ----------


async def test_partida_so_fecha_apos_3_tentativas_confirmadas_dos_dois_lados(db_session):
    coordenador = await _criar_coordenador(db_session, "c22@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a22@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # equipe_a lanca os 3 combates; equipe_b so lanca o combate 1 (que ela
    # vence). A partida nao pode fechar so com esse combate isolado - precisa
    # dos 3 combates confirmados dos DOIS lados antes de decidir.
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 5, tentativa=1
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 9, tentativa=1
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 5, tentativa=2
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 5, tentativa=3
    )

    partida_meio = await db_session.get(Partida, partida.id)
    assert partida_meio.status == PartidaStatus.AGENDADA


async def test_vencedor_da_partida_e_quem_ganha_2_dos_3_combates(db_session):
    coordenador = await _criar_coordenador(db_session, "c23@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a23@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # combate 1: equipe_b vence disparado (1x9); combate 2 e 3: equipe_a vence
    # por pouco (2x1) -> equipe_a fecha a partida 2x1 mesmo perdendo o combate
    # 1 de goleada (prova que e por NUMERO de combates vencidos, nao por soma
    # de pontos - uma comparacao ingenua so do primeiro combate confirmado
    # de cada lado apontaria equipe_b como vencedora, o que seria errado).
    for tentativa, (pontos_a, pontos_b) in enumerate([(1, 9), (2, 1), (2, 1)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_a.id


async def test_combate_empatado_nao_conta_vitoria_pra_ninguem(db_session):
    coordenador = await _criar_coordenador(db_session, "c24@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a24@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # combate 1: empate (nao conta pra ninguem); combate 2 e 3: equipe_b vence
    # -> 2x0 pra equipe_b. Os valores sao escolhidos pra que uma comparacao
    # ingenua (so o 1o par de lancamentos confirmados de cada lado, sem
    # respeitar a tentativa) apontasse equipe_a como vencedora - o que seria
    # errado, ja que equipe_b venceu 2 dos 3 combates de verdade.
    for tentativa, (pontos_a, pontos_b) in enumerate([(2, 2), (5, 9), (1, 9)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_b.id


async def test_partida_mata_mata_fica_aberta_se_combates_empatam_1_1(db_session):
    coordenador = await _criar_coordenador(db_session, "c25@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a25@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # combate 1: equipe_a vence; combate 2: equipe_b vence; combate 3: empate -> 1x1, sem vencedor
    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.AGENDADA
    assert partida_final.vencedor_id is None


async def test_mata_mata_combate_extra_de_desempate_fecha_a_partida(db_session):
    """Quando os 3 combates empatam 1x1 (com 1 combate empatado no meio), um
    combate extra na tentativa seguinte (tentativas_por_rodada + 1) decide a
    partida sem reescrever o resultado dos 3 combates anteriores - e o
    'ponto de ouro' descrito no CLAUDE.md, nao uma correcao de lancamento.
    """
    coordenador = await _criar_coordenador(db_session, "c27@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a27@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_antes = await db_session.get(Partida, partida.id)
    assert partida_antes.status == PartidaStatus.AGENDADA  # ainda 1x1, precisa do desempate

    # combate extra (tentativa 4): equipe_b vence -> decide a partida 2x1
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 1, tentativa=4
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 8, tentativa=4
    )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_b.id


async def test_mata_mata_combate_extra_tambem_empatado_mantem_partida_aberta(db_session):
    coordenador = await _criar_coordenador(db_session, "c28@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a28@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    # combate extra tambem empata -> continua sem vencedor (fica pro coordenador resolver)
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 4, tentativa=4
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 4, tentativa=4
    )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.AGENDADA
    assert partida_final.vencedor_id is None


async def test_todos_contra_todos_marca_empatada_quando_combates_empatam(db_session):
    coordenador = await _criar_coordenador(db_session, "c26@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a26@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS, tentativas_por_rodada=3
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    # combate 1: equipe[0] vence; combate 2: equipe[1] vence; combate 3: empate -> 1x1, EMPATADA
    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[0],
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[1],
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.EMPATADA
    assert partida_final.vencedor_id is None


async def test_soma_pontos_decide_vencedor_pelo_total_mesmo_com_1_combate_vencido_cada(db_session):
    """Reproduz o cenario relatado: cada equipe vence 1 combate (1 a 1 na
    contagem, que empataria em COMBATES_VENCIDOS), mas o total de pontos
    somado dos 2 combates e diferente - com decisao_partida=SOMA_PONTOS a
    equipe com mais pontos no total vence a partida, nao empata.
    """
    coordenador = await _criar_coordenador(db_session, "c27soma@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a27soma@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session,
        formato=FormatoChaveamento.TODOS_CONTRA_TODOS,
        tentativas_por_rodada=2,
        decisao_partida=DecisaoPartida.SOMA_PONTOS,
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    # combate 1: equipe[0] vence 20x0; combate 2: equipe[1] vence 0x10.
    # 1 combate vencido cada (empataria em COMBATES_VENCIDOS), mas a soma dos
    # totais (20+0=20 contra 0+10=10) da vitoria pra equipe[0].
    for tentativa, (ocorrencias_a, ocorrencias_b) in enumerate([(2, 0), (0, 1)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[0],
            criterio,
            partida,
            arbitro,
            ocorrencias_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[1],
            criterio,
            partida,
            arbitro,
            ocorrencias_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipes[0].id


async def test_soma_pontos_mata_mata_usa_ponto_de_ouro_quando_soma_tambem_empata(db_session):
    coordenador = await _criar_coordenador(db_session, "c28soma@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a28soma@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session,
        formato=FormatoChaveamento.MATA_MATA,
        tentativas_por_rodada=2,
        decisao_partida=DecisaoPartida.SOMA_PONTOS,
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    # combate 1: equipe[0] 20x0; combate 2: equipe[1] 0x20 -> soma 20x20, empata
    for tentativa, (ocorrencias_a, ocorrencias_b) in enumerate([(2, 0), (0, 2)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[0],
            criterio,
            partida,
            arbitro,
            ocorrencias_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[1],
            criterio,
            partida,
            arbitro,
            ocorrencias_b,
            tentativa=tentativa,
        )

    partida_apos_normais = await db_session.get(Partida, partida.id)
    assert partida_apos_normais.status == PartidaStatus.AGENDADA

    # ponto de ouro (tentativa 3): equipe[0] marca 10, equipe[1] marca 0 ->
    # soma vira 30x20, equipe[0] vence
    await _lancar_e_confirmar(
        db_session,
        ficha,
        rodada,
        equipes[0],
        criterio,
        partida,
        arbitro,
        1,
        tentativa=3,
    )
    await _lancar_e_confirmar(
        db_session,
        ficha,
        rodada,
        equipes[1],
        criterio,
        partida,
        arbitro,
        0,
        tentativa=3,
    )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipes[0].id


# ---------- resetar_chaveamento ----------


async def test_resetar_chaveamento_recusa_modalidade_individual(db_session):
    coordenador = await _criar_coordenador(db_session, "c27@tjr.app")
    evento = Evento(
        nome="E",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    modalidade = Modalidade(
        evento_id=evento.id,
        nome="Individual",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await resetar_chaveamento(
            db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano"
        )

    assert exc_info.value.codigo == "RESET_APENAS_CONFRONTO"


async def test_resetar_chaveamento_sem_rodada_e_no_op(db_session):
    coordenador = await _criar_coordenador(db_session, "c28@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)

    await resetar_chaveamento(
        db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano"
    )

    resultado = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entidade_id == modalidade.id, AuditLog.acao == "RESET_CHAVEAMENTO"
        )
    )
    assert resultado.scalar_one_or_none() is None


async def test_resetar_chaveamento_apaga_tudo_e_grava_snapshot_no_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session, "c29@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a29@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=FormatoChaveamento.MATA_MATA)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
    partida = resultado.scalars().first()

    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 5, tentativa=1
    )

    await resetar_chaveamento(
        db_session,
        modalidade.id,
        usuario_id=coordenador.id,
        justificativa="Coordenacao pediu mata-mata, mas o formato certo era todos-contra-todos.",
    )

    assert (await db_session.get(Rodada, rodada.id)) is None
    assert (await db_session.get(Partida, partida.id)) is None
    resultado = await db_session.execute(
        select(Lancamento).where(Lancamento.rodada_id == rodada.id)
    )
    assert resultado.scalars().all() == []
    resultado = await db_session.execute(
        select(LancamentoItem).join(Lancamento).where(Lancamento.rodada_id == rodada.id)
    )
    assert resultado.scalars().all() == []

    resultado = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entidade_id == modalidade.id, AuditLog.acao == "RESET_CHAVEAMENTO"
        )
    )
    log = resultado.scalar_one()
    assert log.justificativa.startswith("Coordenacao pediu mata-mata")
    assert len(log.antes["rodadas"]) == 1
    assert len(log.antes["partidas"]) == 2
    assert len(log.antes["lancamentos"]) == 1
    assert len(log.antes["itens"]) == 1


async def test_resetar_chaveamento_libera_trocar_formato_e_gerar_de_novo(db_session):
    coordenador = await _criar_coordenador(db_session, "c30@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=FormatoChaveamento.MATA_MATA)
    await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)

    await resetar_chaveamento(
        db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano de formato"
    )

    atualizada = await atualizar_modalidade(
        db_session,
        modalidade.id,
        ModalidadeUpdate(formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS),
        usuario_id=coordenador.id,
    )
    assert atualizada.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS

    # todos-contra-todos gera rodadas pelo returno manual (gerar_rodadas), nao
    # pelo gerar_chaveamento_inicial (esse so vale pra MATA_MATA)
    novas_rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)
    assert len(novas_rodadas) > 0
    assert novas_rodadas[0].numero == 1
