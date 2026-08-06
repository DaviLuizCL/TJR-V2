import uuid
from datetime import date

import pytest

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.inscricao import Inscricao
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.partida import Partida
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.services.rodada import gerar_rodadas, listar_rodadas


async def _criar_coordenador(db_session, email="coord-gerar-rodadas@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(
    db_session, *, tipo_disputa=TipoDisputa.INDIVIDUAL, qtd_rodadas=3, nome="Modalidade Teste"
) -> Modalidade:
    evento = Evento(
        nome="TJR 2026",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()

    modalidade = Modalidade(
        evento_id=evento.id,
        nome=nome,
        tipo_disputa=tipo_disputa,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=qtd_rodadas,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever_equipes(db_session, modalidade, quantidade) -> list[Equipe]:
    equipes = []
    for i in range(quantidade):
        equipe = Equipe(nome=f"Equipe {i + 1}", nivel=1)
        db_session.add(equipe)
        await db_session.flush()
        db_session.add(Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id))
        equipes.append(equipe)
    await db_session.flush()
    return equipes


async def test_gerar_rodadas_com_modalidade_inexistente_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await gerar_rodadas(db_session, uuid.uuid4(), usuario_id=coordenador.id)

    assert exc_info.value.codigo == "MODALIDADE_NAO_ENCONTRADA"


async def test_gerar_rodadas_cria_as_que_faltam(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, qtd_rodadas=3)

    rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    assert [r.numero for r in rodadas] == [1, 2, 3]
    assert all(r.status == RodadaStatus.AGENDADA for r in rodadas)
    assert all(r.modo_horario == ModoHorario.AUTOMATICO for r in rodadas)


async def test_gerar_rodadas_preserva_rodada_existente(db_session):
    from datetime import UTC, datetime

    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, qtd_rodadas=3)
    existente = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        horario_inicio=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(existente)
    await db_session.flush()

    rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    assert len(rodadas) == 3
    rodada_1 = next(r for r in rodadas if r.numero == 1)
    assert rodada_1.id == existente.id
    assert rodada_1.modo_horario == ModoHorario.MANUAL


async def test_gerar_rodadas_individual_nao_gera_partidas(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, tipo_disputa=TipoDisputa.INDIVIDUAL, qtd_rodadas=2
    )
    await _inscrever_equipes(db_session, modalidade, 4)

    rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    from sqlalchemy import select

    for rodada in rodadas:
        resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
        assert resultado.scalars().all() == []


async def test_gerar_rodadas_confronto_gera_partidas_para_numero_par_de_equipes(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, tipo_disputa=TipoDisputa.CONFRONTO, qtd_rodadas=3
    )
    equipes = await _inscrever_equipes(db_session, modalidade, 4)
    ids_equipes = {e.id for e in equipes}

    rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    from sqlalchemy import select

    todos_os_pares = []
    for rodada in rodadas:
        resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
        partidas = resultado.scalars().all()
        assert len(partidas) == 2

        equipes_na_rodada = []
        for partida in partidas:
            equipes_na_rodada.extend([partida.equipe_a_id, partida.equipe_b_id])
            todos_os_pares.append(frozenset({partida.equipe_a_id, partida.equipe_b_id}))
        assert set(equipes_na_rodada) == ids_equipes

    # com 4 equipes e 3 rodadas (n-1), o metodo do circulo garante nenhum par repetido
    assert len(todos_os_pares) == len(set(todos_os_pares))


async def test_gerar_rodadas_confronto_numero_impar_deixa_uma_equipe_de_bye(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, tipo_disputa=TipoDisputa.CONFRONTO, qtd_rodadas=1
    )
    await _inscrever_equipes(db_session, modalidade, 3)

    rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    from sqlalchemy import select

    resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodadas[0].id))
    partidas = resultado.scalars().all()
    assert len(partidas) == 1


async def test_gerar_rodadas_confronto_separa_por_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, tipo_disputa=TipoDisputa.CONFRONTO, qtd_rodadas=3
    )
    equipes_nivel1 = []
    for i in range(4):
        equipe = Equipe(nome=f"N1 Equipe {i + 1}", nivel=1)
        db_session.add(equipe)
        await db_session.flush()
        db_session.add(Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id))
        equipes_nivel1.append(equipe)
    equipes_nivel2 = []
    for i in range(2):
        equipe = Equipe(nome=f"N2 Equipe {i + 1}", nivel=2)
        db_session.add(equipe)
        await db_session.flush()
        db_session.add(Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id))
        equipes_nivel2.append(equipe)
    await db_session.flush()
    ids_nivel1 = {e.id for e in equipes_nivel1}

    rodadas = await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    from sqlalchemy import select

    todas_partidas_por_rodada = {}
    for rodada in rodadas:
        resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
        todas_partidas_por_rodada[rodada.numero] = resultado.scalars().all()

    # nenhuma partida cruza nivel, e toda partida tem o nivel marcado certo
    for partidas in todas_partidas_por_rodada.values():
        for partida in partidas:
            lado_a_no_nivel1 = partida.equipe_a_id in ids_nivel1
            lado_b_no_nivel1 = partida.equipe_b_id in ids_nivel1
            assert lado_a_no_nivel1 == lado_b_no_nivel1
            assert partida.nivel == (1 if lado_a_no_nivel1 else 2)

    # nivel 2 (2 equipes) so precisa de 1 rodada; nivel 1 (4 equipes) precisa
    # de 3 (com 2 partidas simultaneas por rodada, 4/2). Na rodada 3, so deve
    # sobrar partida do nivel 1 (nivel 2 ja esgotou seu unico confronto).
    partidas_rodada_3 = todas_partidas_por_rodada[3]
    assert len(partidas_rodada_3) == 2
    assert all(p.nivel == 1 for p in partidas_rodada_3)


async def test_gerar_rodadas_nao_duplica_partidas_ja_geradas(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, tipo_disputa=TipoDisputa.CONFRONTO, qtd_rodadas=2
    )
    await _inscrever_equipes(db_session, modalidade, 4)

    await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)
    await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    rodadas = await listar_rodadas(db_session, modalidade_id=modalidade.id, page=1, size=50)

    from sqlalchemy import select

    for rodada in rodadas[0]:
        resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
        assert len(resultado.scalars().all()) == 2
