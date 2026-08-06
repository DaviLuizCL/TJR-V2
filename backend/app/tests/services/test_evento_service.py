from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.evento import EventoStatus
from app.models.usuario import Papel, Usuario
from app.schemas.evento import EventoCreate, EventoUpdate
from app.services.evento import atualizar_evento, criar_evento, listar_eventos, obter_evento


async def _criar_coordenador(db_session) -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email="coord-evento-service@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def test_criar_evento_nasce_em_rascunho(db_session):
    coordenador = await _criar_coordenador(db_session)
    dto = EventoCreate(
        nome="TJR 2026", ano=2026, data_inicio=date(2026, 3, 10), data_fim=date(2026, 3, 12)
    )

    evento = await criar_evento(db_session, dto, usuario_id=coordenador.id)

    assert evento.status == EventoStatus.RASCUNHO
    assert evento.id is not None


async def test_criar_evento_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    dto = EventoCreate(
        nome="TJR 2026", ano=2026, data_inicio=date(2026, 3, 10), data_fim=date(2026, 3, 12)
    )

    evento = await criar_evento(db_session, dto, usuario_id=coordenador.id)

    resultado = await db_session.execute(select(AuditLog).where(AuditLog.entidade_id == evento.id))
    log = resultado.scalar_one()

    assert log.entidade == "evento"
    assert log.acao == "CRIAR"
    assert log.antes is None
    assert log.depois["nome"] == "TJR 2026"


async def test_criar_evento_rejeita_data_fim_antes_de_inicio(db_session):
    coordenador = await _criar_coordenador(db_session)
    dto = EventoCreate(
        nome="TJR Invalido", ano=2026, data_inicio=date(2026, 3, 12), data_fim=date(2026, 3, 10)
    )

    with pytest.raises(AppError) as exc_info:
        await criar_evento(db_session, dto, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "DATA_FIM_ANTES_DE_INICIO"


async def test_obter_evento_inexistente_lanca_erro(db_session):
    import uuid

    with pytest.raises(AppError) as exc_info:
        await obter_evento(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "EVENTO_NAO_ENCONTRADO"
    assert exc_info.value.status_code == 404


async def test_listar_eventos_pagina_resultados(db_session):
    coordenador = await _criar_coordenador(db_session)
    for i in range(3):
        await criar_evento(
            db_session,
            EventoCreate(
                nome=f"Evento {i}",
                ano=2026,
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 1, 2),
            ),
            usuario_id=coordenador.id,
        )

    itens, total = await listar_eventos(db_session, page=1, size=2)

    assert total == 3
    assert len(itens) == 2


async def test_atualizar_evento_altera_campos_e_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    evento = await criar_evento(
        db_session,
        EventoCreate(
            nome="Nome Original", ano=2026, data_inicio=date(2026, 1, 1), data_fim=date(2026, 1, 2)
        ),
        usuario_id=coordenador.id,
    )

    atualizado = await atualizar_evento(
        db_session, evento.id, EventoUpdate(nome="Nome Corrigido"), usuario_id=coordenador.id
    )

    assert atualizado.nome == "Nome Corrigido"

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == evento.id, AuditLog.acao == "ATUALIZAR")
    )
    log = resultado.scalar_one()
    assert log.antes["nome"] == "Nome Original"
    assert log.depois["nome"] == "Nome Corrigido"


async def test_atualizar_evento_rejeita_data_fim_antes_de_inicio(db_session):
    coordenador = await _criar_coordenador(db_session)
    evento = await criar_evento(
        db_session,
        EventoCreate(
            nome="Evento X", ano=2026, data_inicio=date(2026, 1, 1), data_fim=date(2026, 1, 5)
        ),
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await atualizar_evento(
            db_session,
            evento.id,
            EventoUpdate(data_fim=date(2025, 12, 31)),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "DATA_FIM_ANTES_DE_INICIO"
