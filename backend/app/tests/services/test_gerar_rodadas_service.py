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


async def test_gerar_rodadas_recusa_modalidade_de_confronto(db_session):
    # Confronto e montado 100% na mao (criar_partida_manual) - nenhum
    # pareamento automatico, nem round-robin.
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, tipo_disputa=TipoDisputa.CONFRONTO, qtd_rodadas=3
    )
    await _inscrever_equipes(db_session, modalidade, 4)

    with pytest.raises(AppError) as exc:
        await gerar_rodadas(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc.value.codigo == "GERAR_RODADAS_SO_INDIVIDUAL"
    assert await listar_rodadas(db_session, modalidade_id=modalidade.id, page=1, size=50) == ([], 0)
