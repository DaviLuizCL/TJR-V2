import pytest
from pydantic import ValidationError

from app.models.modalidade import Consolidacao, TipoDisputa
from app.schemas.modalidade import ModalidadeCreate


def _payload(**overrides):
    base = dict(
        evento_id="11111111-1111-1111-1111-111111111111",
        nome="Sumo de Robos",
        tipo_disputa=TipoDisputa.CONFRONTO,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=3,
        consolidacao=Consolidacao.SOMA_RODADAS,
    )
    base.update(overrides)
    return base


def test_modalidade_create_aplica_defaults():
    dto = ModalidadeCreate(**_payload())

    assert dto.tentativas_por_rodada == 1
    assert dto.permite_total_negativo is False
    assert dto.desempates is None


def test_modalidade_create_rejeita_qtd_rodadas_zero():
    with pytest.raises(ValidationError):
        ModalidadeCreate(**_payload(qtd_rodadas=0))


def test_modalidade_create_rejeita_tipo_disputa_fora_do_enum():
    with pytest.raises(ValidationError):
        ModalidadeCreate(**_payload(tipo_disputa="FOO"))


def test_modalidade_create_rejeita_tentativas_por_rodada_zero():
    with pytest.raises(ValidationError):
        ModalidadeCreate(**_payload(tentativas_por_rodada=0))


def test_modalidade_create_rejeita_nome_so_com_espacos():
    with pytest.raises(ValidationError):
        ModalidadeCreate(**_payload(nome="   "))


def test_modalidade_create_tira_espaco_das_pontas_do_nome():
    dto = ModalidadeCreate(**_payload(nome="  Sumo de Robos  "))

    assert dto.nome == "Sumo de Robos"
