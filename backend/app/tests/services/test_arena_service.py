from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.usuario import Papel, Usuario
from app.schemas.arena import ArenaCreate, ArenaUpdate
from app.services.arena import (
    atualizar_arena,
    criar_arena,
    listar_arenas,
    obter_arena,
)


async def _criar_coordenador(db_session, email="coord-arena@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(
    db_session,
    *,
    tipo_disputa=TipoDisputa.INDIVIDUAL,
    niveis_aplicaveis=None,
) -> Modalidade:
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
        nome="Resgate no Plano",
        tipo_disputa=tipo_disputa,
        niveis_aplicaveis=niveis_aplicaveis or [1, 2, 3, 4],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=3,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def test_criar_arena_aberta_a_qualquer_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)

    arena = await criar_arena(
        db_session,
        ArenaCreate(modalidade_id=modalidade.id, nome="Arena 1"),
        usuario_id=coordenador.id,
    )

    assert arena.niveis_aplicaveis is None
    assert arena.ativo is True


async def test_criar_arena_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)

    arena = await criar_arena(
        db_session,
        ArenaCreate(modalidade_id=modalidade.id, nome="Arena 1"),
        usuario_id=coordenador.id,
    )

    resultado = await db_session.execute(select(AuditLog).where(AuditLog.entidade_id == arena.id))
    log = resultado.scalar_one()
    assert log.entidade == "arena"
    assert log.acao == "CRIAR"


async def test_criar_arena_com_niveis_subconjunto_da_modalidade(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2, 3, 4])

    arena = await criar_arena(
        db_session,
        ArenaCreate(
            modalidade_id=modalidade.id, nome="Arena Nivel 1 e 2", niveis_aplicaveis=[1, 2]
        ),
        usuario_id=coordenador.id,
    )

    assert arena.niveis_aplicaveis == [1, 2]


async def test_criar_arena_rejeita_nivel_fora_do_conjunto_da_modalidade(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])

    with pytest.raises(AppError) as exc_info:
        await criar_arena(
            db_session,
            ArenaCreate(modalidade_id=modalidade.id, nome="Arena Nivel 3", niveis_aplicaveis=[3]),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "ARENA_NIVEL_FORA_DA_MODALIDADE"


async def test_criar_arena_rejeita_em_modalidade_confronto(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, tipo_disputa=TipoDisputa.CONFRONTO)

    with pytest.raises(AppError) as exc_info:
        await criar_arena(
            db_session,
            ArenaCreate(modalidade_id=modalidade.id, nome="Arena 1"),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "MODALIDADE_NAO_E_INDIVIDUAL"


async def test_obter_arena_inexistente_lanca_erro(db_session):
    import uuid

    with pytest.raises(AppError) as exc_info:
        await obter_arena(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "ARENA_NAO_ENCONTRADA"


async def test_listar_arenas_filtra_por_modalidade_e_ativo(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade_a = await _criar_modalidade(db_session)
    modalidade_b = await _criar_modalidade(db_session)

    arena_a1 = await criar_arena(
        db_session, ArenaCreate(modalidade_id=modalidade_a.id, nome="A1"), usuario_id=coordenador.id
    )
    await criar_arena(
        db_session,
        ArenaCreate(modalidade_id=modalidade_a.id, nome="A2", ativo=False),
        usuario_id=coordenador.id,
    )
    await criar_arena(
        db_session, ArenaCreate(modalidade_id=modalidade_b.id, nome="B1"), usuario_id=coordenador.id
    )

    itens, total = await listar_arenas(
        db_session, modalidade_id=modalidade_a.id, ativo=True, page=1, size=50
    )

    assert total == 1
    assert itens[0].id == arena_a1.id


async def test_atualizar_arena_altera_campos_e_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    arena = await criar_arena(
        db_session,
        ArenaCreate(modalidade_id=modalidade.id, nome="Arena 1"),
        usuario_id=coordenador.id,
    )

    atualizada = await atualizar_arena(
        db_session, arena.id, ArenaUpdate(ativo=False), usuario_id=coordenador.id
    )

    assert atualizada.ativo is False

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == arena.id, AuditLog.acao == "ATUALIZAR")
    )
    log = resultado.scalar_one()
    assert log.antes["ativo"] is True
    assert log.depois["ativo"] is False
