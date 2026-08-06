import uuid

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.usuario import Papel, Usuario
from app.schemas.equipe import EquipeCreate, EquipeUpdate
from app.services.equipe import (
    atualizar_equipe,
    criar_equipe,
    listar_equipes,
    obter_equipe,
)


async def _criar_coordenador(db_session, email="coord-equipe-service@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


def _payload(**overrides):
    base = dict(nome="Equipe Alpha", nivel=2)
    base.update(overrides)
    return EquipeCreate(**base)


async def test_criar_equipe_nasce_ativa(db_session):
    coordenador = await _criar_coordenador(db_session)
    equipe = await criar_equipe(db_session, _payload(), usuario_id=coordenador.id)

    assert equipe.ativo is True
    assert equipe.nome == "Equipe Alpha"
    assert equipe.nivel == 2


async def test_criar_equipe_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    equipe = await criar_equipe(db_session, _payload(), usuario_id=coordenador.id)

    resultado = await db_session.execute(select(AuditLog).where(AuditLog.entidade_id == equipe.id))
    log = resultado.scalar_one()
    assert log.entidade == "equipe"
    assert log.acao == "CRIAR"


async def test_obter_equipe_inexistente_lanca_erro(db_session):
    with pytest.raises(AppError) as exc_info:
        await obter_equipe(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "EQUIPE_NAO_ENCONTRADA"


async def test_listar_equipes_filtra_por_nivel(db_session):
    usuario_id = (await _criar_coordenador(db_session)).id
    await criar_equipe(db_session, _payload(nome="N1", nivel=1), usuario_id=usuario_id)
    await criar_equipe(db_session, _payload(nome="N2-a", nivel=2), usuario_id=usuario_id)
    await criar_equipe(db_session, _payload(nome="N2-b", nivel=2), usuario_id=usuario_id)

    itens, total = await listar_equipes(db_session, nivel=2, ativo=None, page=1, size=50)

    assert total == 2
    assert {e.nome for e in itens} == {"N2-a", "N2-b"}


async def test_listar_equipes_filtra_por_ativo(db_session):
    usuario_id = (await _criar_coordenador(db_session)).id
    ativa = await criar_equipe(db_session, _payload(nome="Ativa"), usuario_id=usuario_id)
    inativa = await criar_equipe(db_session, _payload(nome="Inativa"), usuario_id=usuario_id)
    await atualizar_equipe(db_session, inativa.id, EquipeUpdate(ativo=False), usuario_id=usuario_id)

    itens, total = await listar_equipes(db_session, nivel=None, ativo=True, page=1, size=50)

    assert total == 1
    assert itens[0].id == ativa.id


async def test_atualizar_equipe_altera_nome_e_grava_audit_log(db_session):
    usuario_id = (await _criar_coordenador(db_session)).id
    equipe = await criar_equipe(db_session, _payload(), usuario_id=usuario_id)

    atualizada = await atualizar_equipe(
        db_session, equipe.id, EquipeUpdate(nome="Equipe Beta"), usuario_id=usuario_id
    )

    assert atualizada.nome == "Equipe Beta"

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == equipe.id, AuditLog.acao == "ATUALIZAR")
    )
    log = resultado.scalar_one()
    assert log.antes["nome"] == "Equipe Alpha"
    assert log.depois["nome"] == "Equipe Beta"


async def test_atualizar_equipe_inativa_desliga_ativo(db_session):
    usuario_id = (await _criar_coordenador(db_session)).id
    equipe = await criar_equipe(db_session, _payload(), usuario_id=usuario_id)

    atualizada = await atualizar_equipe(
        db_session, equipe.id, EquipeUpdate(ativo=False), usuario_id=usuario_id
    )

    assert atualizada.ativo is False
