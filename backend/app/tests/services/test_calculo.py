import uuid
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo, ModificadorTipo
from app.models.ficha import Ficha
from app.models.grupo import Grupo
from app.models.modalidade import Modalidade
from app.schemas.simulacao import SimulacaoRequest, ValorCriterioSimulado
from app.services.calculo import calcular


def _criterio(**kwargs) -> Criterio:
    defaults = dict(
        id=uuid.uuid4(),
        grupo_id=uuid.uuid4(),
        ordem=1,
        ativo=True,
        descricao=None,
        categoria=CategoriaCriterio.PONTUACAO,
    )
    defaults.update(kwargs)
    return Criterio(**defaults)


def _ficha_com_grupo(*criterios) -> Ficha:
    ficha = Ficha(id=uuid.uuid4(), modalidade_id=uuid.uuid4(), nivel=1, versao=1)
    grupo = Grupo(id=uuid.uuid4(), ficha_id=ficha.id, nome="Grupo Unico", ordem=1)
    grupo.criterios = list(criterios)
    ficha.grupos = [grupo]
    return ficha


def _modalidade(*, permite_total_negativo=False) -> Modalidade:
    return Modalidade(id=uuid.uuid4(), permite_total_negativo=permite_total_negativo)


def test_calculo_soma_contador_booleano_e_escala_sem_penalidade():
    contador = _criterio(nome="Lombada", tipo=CriterioTipo.CONTADOR, pontos=Decimal("10"))
    booleano = _criterio(nome="Finalizacao", tipo=CriterioTipo.BOOLEANO, pontos=Decimal("50"))
    escala = _criterio(
        nome="Nota Artistica", tipo=CriterioTipo.ESCALA, valores_permitidos=[0, 2, 5, 7, 10]
    )
    ficha = _ficha_com_grupo(contador, booleano, escala)
    modalidade = _modalidade()

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=contador.id, ocorrencias=3),
            ValorCriterioSimulado(criterio_id=booleano.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=escala.id, valor=7),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    assert resultado.total == 30 + 50 + 7


def test_calculo_contador_com_max_ocorrencias_estourado_lanca_erro():
    contador = _criterio(
        nome="Lombada", tipo=CriterioTipo.CONTADOR, pontos=Decimal("10"), max_ocorrencias=3
    )
    ficha = _ficha_com_grupo(contador)
    modalidade = _modalidade()

    dto = SimulacaoRequest(valores=[ValorCriterioSimulado(criterio_id=contador.id, ocorrencias=5)])

    with pytest.raises(AppError) as exc_info:
        calcular(ficha, modalidade, dto)

    assert exc_info.value.codigo == "CRITERIO_MAX_OCORRENCIAS_EXCEDIDO"


def test_calculo_escala_com_valor_invalido_lanca_erro():
    escala = _criterio(
        nome="Nota Artistica", tipo=CriterioTipo.ESCALA, valores_permitidos=[0, 2, 5, 7, 10]
    )
    ficha = _ficha_com_grupo(escala)
    modalidade = _modalidade()

    dto = SimulacaoRequest(valores=[ValorCriterioSimulado(criterio_id=escala.id, valor=3)])

    with pytest.raises(AppError) as exc_info:
        calcular(ficha, modalidade, dto)

    assert exc_info.value.codigo == "CRITERIO_VALOR_FORA_DA_ESCALA"


def test_calculo_penalidade_zera_o_total_sem_permitir_negativo():
    base = _criterio(nome="Base", tipo=CriterioTipo.CONTADOR, pontos=Decimal("10"))
    colisao = _criterio(
        nome="Colisao",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("20"),
    )
    ficha = _ficha_com_grupo(base, colisao)
    modalidade = _modalidade(permite_total_negativo=False)

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=base.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=colisao.id, ocorrencias=1),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    assert resultado.total == 0


def test_calculo_permite_total_negativo_quando_modalidade_marca():
    base = _criterio(nome="Base", tipo=CriterioTipo.CONTADOR, pontos=Decimal("10"))
    colisao = _criterio(
        nome="Colisao",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("20"),
    )
    ficha = _ficha_com_grupo(base, colisao)
    modalidade = _modalidade(permite_total_negativo=True)

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=base.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=colisao.id, ocorrencias=1),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    assert resultado.total == -10


def test_calculo_criterio_booleano_penalidade_subtrai_do_total():
    base = _criterio(nome="Base", tipo=CriterioTipo.CONTADOR, pontos=Decimal("100"))
    saiu_area = _criterio(
        nome="Saiu da area",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.BOOLEANO,
        pontos=Decimal("15"),
    )
    ficha = _ficha_com_grupo(base, saiu_area)
    modalidade = _modalidade()

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=base.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=saiu_area.id, ocorrencias=1),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    assert resultado.total == 85


def test_calculo_modificador_percentual_sobre_total_com_penalidade():
    base = _criterio(nome="Base", tipo=CriterioTipo.CONTADOR, pontos=Decimal("100"))
    colisao = _criterio(
        nome="Colisao",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("20"),
    )
    excedeu_tempo = _criterio(
        nome="Excedeu tempo",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.MODIFICADOR,
        modificador_tipo=ModificadorTipo.PERCENTUAL,
        modificador_valor=Decimal("10"),
    )
    ficha = _ficha_com_grupo(base, colisao, excedeu_tempo)
    modalidade = _modalidade()

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=base.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=colisao.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=excedeu_tempo.id, aplicado=True),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    # (100 - 20) * (1 - 10/100) = 80 * 0.9 = 72
    assert resultado.total == 72
    assert len(resultado.modificadores_aplicados) == 1


def test_calculo_modificador_pontuacao_aplica_bonus_percentual():
    base = _criterio(nome="Base", tipo=CriterioTipo.CONTADOR, pontos=Decimal("100"))
    bonus_tempo = _criterio(
        nome="Terminou no tempo",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.MODIFICADOR,
        modificador_tipo=ModificadorTipo.PERCENTUAL,
        modificador_valor=Decimal("10"),
    )
    ficha = _ficha_com_grupo(base, bonus_tempo)
    modalidade = _modalidade()

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=base.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=bonus_tempo.id, aplicado=True),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    # 100 * (1 + 10/100) = 110
    assert resultado.total == 110


def test_calculo_zera_total_prevalece_sobre_percentual():
    base = _criterio(nome="Base", tipo=CriterioTipo.CONTADOR, pontos=Decimal("100"))
    percentual = _criterio(
        nome="Excedeu tempo",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.MODIFICADOR,
        modificador_tipo=ModificadorTipo.PERCENTUAL,
        modificador_valor=Decimal("50"),
    )
    paralisacao = _criterio(
        nome="Paralisacao",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.MODIFICADOR,
        modificador_tipo=ModificadorTipo.ZERA_TOTAL,
    )
    ficha = _ficha_com_grupo(base, percentual, paralisacao)
    modalidade = _modalidade()

    dto = SimulacaoRequest(
        valores=[
            ValorCriterioSimulado(criterio_id=base.id, ocorrencias=1),
            ValorCriterioSimulado(criterio_id=percentual.id, aplicado=True),
            ValorCriterioSimulado(criterio_id=paralisacao.id, aplicado=True),
        ]
    )

    resultado = calcular(ficha, modalidade, dto)

    assert resultado.total == 0
