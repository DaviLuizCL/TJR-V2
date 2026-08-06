import pytest
from sqlalchemy.exc import IntegrityError

from app.models.ficha import Ficha, FichaStatus


async def test_criar_ficha_versao_1_para_nivel_1(db_session, modalidade):
    obj = Ficha(modalidade_id=modalidade.id, nivel=1, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(obj)
    await db_session.flush()

    assert obj.id is not None
    assert obj.publicada_em is None


async def test_ficha_nivel_nulo_vale_para_todos_os_niveis(db_session, modalidade):
    obj = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(obj)
    await db_session.flush()

    assert obj.nivel is None


async def test_ficha_impede_duas_versoes_iguais_para_mesmo_nivel(db_session, modalidade):
    db_session.add(
        Ficha(modalidade_id=modalidade.id, nivel=1, versao=1, status=FichaStatus.RASCUNHO)
    )
    await db_session.flush()

    db_session.add(
        Ficha(modalidade_id=modalidade.id, nivel=1, versao=1, status=FichaStatus.RASCUNHO)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_ficha_permite_duas_versoes_diferentes_para_mesmo_nivel(db_session, modalidade):
    db_session.add(
        Ficha(modalidade_id=modalidade.id, nivel=1, versao=1, status=FichaStatus.SUBSTITUIDA)
    )
    await db_session.flush()

    db_session.add(
        Ficha(modalidade_id=modalidade.id, nivel=1, versao=2, status=FichaStatus.PUBLICADA)
    )
    await db_session.flush()
