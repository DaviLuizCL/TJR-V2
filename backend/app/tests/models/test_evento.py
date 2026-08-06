from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.models.evento import Evento, EventoStatus


async def test_criar_evento_com_campos_basicos(db_session):
    obj = Evento(
        nome="TJR 2026",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(obj)
    await db_session.flush()

    resultado = await db_session.execute(select(Evento).where(Evento.nome == "TJR 2026"))
    salvo = resultado.scalar_one()

    assert salvo.ano == 2026
    assert salvo.status == EventoStatus.RASCUNHO
    assert salvo.id is not None
    assert salvo.criado_em is not None
    assert salvo.atualizado_em is not None


async def test_evento_rejeita_status_fora_do_enum(db_session):
    obj = Evento(
        nome="Evento Invalido",
        ano=2026,
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 1, 2),
        status="NAO_EXISTE",
    )
    db_session.add(obj)

    with pytest.raises(DBAPIError):
        await db_session.flush()
