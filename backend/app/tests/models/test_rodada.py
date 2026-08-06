from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import DBAPIError

from app.models.rodada import ModoHorario, Rodada, RodadaStatus


async def test_criar_rodada_manual_sem_horario(db_session, modalidade):
    obj = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(obj)
    await db_session.flush()

    assert obj.horario_inicio is None


async def test_criar_rodada_automatica_com_horario(db_session, modalidade):
    horario = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
    obj = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        horario_inicio=horario,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(obj)
    await db_session.flush()
    await db_session.refresh(obj)

    assert obj.horario_inicio == horario


async def test_rodada_aceita_transicao_para_em_andamento_e_encerrada(db_session, modalidade):
    obj = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(obj)
    await db_session.flush()

    obj.status = RodadaStatus.EM_ANDAMENTO
    await db_session.flush()
    obj.status = RodadaStatus.ENCERRADA
    await db_session.flush()

    assert obj.status == RodadaStatus.ENCERRADA


async def test_rodada_rejeita_status_fora_do_enum(db_session, modalidade):
    obj = Rodada(
        modalidade_id=modalidade.id, numero=1, modo_horario=ModoHorario.MANUAL, status="FOO"
    )
    db_session.add(obj)

    with pytest.raises(DBAPIError):
        await db_session.flush()
