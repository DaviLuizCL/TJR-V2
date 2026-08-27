from datetime import date

from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.services.partida import listar_partidas_por_rodada


async def _criar_modalidade(db_session) -> Modalidade:
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
        nome="Sumo",
        tipo_disputa=TipoDisputa.CONFRONTO,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _criar_rodada(db_session, modalidade, numero=1) -> Rodada:
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=numero,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    return rodada


async def _criar_equipe(db_session, nome, nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    return equipe


async def test_listar_partidas_por_rodada_retorna_apenas_da_rodada(db_session):
    modalidade = await _criar_modalidade(db_session)
    rodada_a = await _criar_rodada(db_session, modalidade, numero=1)
    rodada_b = await _criar_rodada(db_session, modalidade, numero=2)
    equipe_a = await _criar_equipe(db_session, "Equipe A")
    equipe_b = await _criar_equipe(db_session, "Equipe B")

    db_session.add(
        Partida(
            rodada_id=rodada_a.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            status=PartidaStatus.AGENDADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada_b.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            status=PartidaStatus.AGENDADA,
        )
    )
    await db_session.flush()

    partidas = await listar_partidas_por_rodada(db_session, rodada_a.id)

    assert len(partidas) == 1
    assert partidas[0].rodada_id == rodada_a.id
