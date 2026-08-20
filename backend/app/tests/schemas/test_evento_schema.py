from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.evento import EventoCreate, EventoUpdate


def test_evento_create_aceita_campos_validos():
    dto = EventoCreate(
        nome="TJR 2026", ano=2026, data_inicio=date(2026, 3, 10), data_fim=date(2026, 3, 12)
    )

    assert dto.nome == "TJR 2026"
    assert dto.ano == 2026


def test_evento_create_rejeita_ano_como_texto():
    with pytest.raises(ValidationError):
        EventoCreate(
            nome="X", ano="nao-e-ano", data_inicio=date(2026, 1, 1), data_fim=date(2026, 1, 2)
        )


def test_evento_update_permite_campos_parciais():
    dto = EventoUpdate(nome="Novo nome")

    assert dto.nome == "Novo nome"
    assert dto.ano is None


def test_evento_update_rejeita_status_fora_do_enum():
    with pytest.raises(ValidationError):
        EventoUpdate(status="FOO")


def test_evento_create_rejeita_nome_so_com_espacos():
    with pytest.raises(ValidationError):
        EventoCreate(
            nome="   ", ano=2026, data_inicio=date(2026, 3, 10), data_fim=date(2026, 3, 12)
        )


def test_evento_create_tira_espaco_das_pontas_do_nome():
    dto = EventoCreate(
        nome="  TJR 2026  ", ano=2026, data_inicio=date(2026, 3, 10), data_fim=date(2026, 3, 12)
    )

    assert dto.nome == "TJR 2026"
