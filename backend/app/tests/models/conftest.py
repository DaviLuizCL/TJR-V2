from datetime import date

import pytest

from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa


@pytest.fixture
async def evento(db_session):
    obj = Evento(
        nome="TJR 2026",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def modalidade(db_session, evento):
    obj = Modalidade(
        evento_id=evento.id,
        nome="Modalidade Teste",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(obj)
    await db_session.flush()
    return obj


@pytest.fixture
async def ficha(db_session, modalidade):
    obj = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(obj)
    await db_session.flush()
    return obj
