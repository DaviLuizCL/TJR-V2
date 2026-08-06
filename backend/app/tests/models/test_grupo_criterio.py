from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError

from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo, ModificadorTipo
from app.models.grupo import Grupo


async def test_criar_grupo_e_criterio_contador(db_session, ficha):
    grupo = Grupo(ficha_id=ficha.id, nome="Parte Tecnica", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        max_ocorrencias=5,
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()

    assert criterio.ativo is True
    assert criterio.pontos == Decimal("10")
    assert criterio.grupo_id == grupo.id


async def test_criterio_escala_aceita_valores_permitidos_em_jsonb(db_session, ficha):
    grupo = Grupo(ficha_id=ficha.id, nome="Parte Artistica", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Nota Artistica",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.ESCALA,
        valores_permitidos=[0, 2, 5, 7, 10],
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()
    await db_session.refresh(criterio)

    assert criterio.valores_permitidos == [0, 2, 5, 7, 10]


async def test_criterio_modificador_percentual(db_session, ficha):
    grupo = Grupo(ficha_id=ficha.id, nome="Penalidades", ordem=2)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Excedeu tempo",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.MODIFICADOR,
        modificador_tipo=ModificadorTipo.PERCENTUAL,
        modificador_valor=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()

    assert criterio.modificador_tipo == ModificadorTipo.PERCENTUAL
    assert criterio.modificador_valor == Decimal("10")


async def test_criterio_contador_pode_ser_categoria_penalidade(db_session, ficha):
    grupo = Grupo(ficha_id=ficha.id, nome="Penalidades", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Colisao",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("20"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()

    assert criterio.categoria == CategoriaCriterio.PENALIDADE
    assert criterio.tipo == CriterioTipo.CONTADOR


async def test_criterio_rejeita_categoria_fora_do_enum(db_session, ficha):
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Invalido",
        categoria="NAO_EXISTE",
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)

    with pytest.raises(DBAPIError):
        await db_session.flush()
