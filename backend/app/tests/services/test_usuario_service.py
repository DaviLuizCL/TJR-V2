import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha, verificar_senha
from app.models.audit_log import AuditLog
from app.models.usuario import Papel, Usuario
from app.schemas.usuario import UsuarioCreate
from app.services.usuario import criar_usuario, listar_usuarios


async def _criar_coordenador(db_session, email="coord-usuario@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def test_criar_usuario_hasheia_a_senha_e_nao_guarda_texto_puro(db_session):
    coordenador = await _criar_coordenador(db_session)
    dto = UsuarioCreate(
        nome="Arbitro Um", email="arbitro-novo@tjr.app", senha="senha-forte", papel=Papel.ARBITRO
    )

    usuario = await criar_usuario(db_session, dto, usuario_id=coordenador.id)

    assert usuario.senha_hash != "senha-forte"
    assert verificar_senha("senha-forte", usuario.senha_hash)
    assert usuario.papel == Papel.ARBITRO
    assert usuario.ativo is True


async def test_criar_usuario_com_email_duplicado_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    dto = UsuarioCreate(
        nome="Arbitro Um", email="duplicado@tjr.app", senha="senha-forte", papel=Papel.ARBITRO
    )
    await criar_usuario(db_session, dto, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await criar_usuario(db_session, dto, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "EMAIL_JA_CADASTRADO"
    assert exc_info.value.status_code == 409


async def test_criar_usuario_grava_audit_log_sem_expor_a_senha(db_session):
    coordenador = await _criar_coordenador(db_session)
    dto = UsuarioCreate(
        nome="Secretaria Um",
        email="secretaria-novo@tjr.app",
        senha="senha-forte",
        papel=Papel.SECRETARIA,
    )

    usuario = await criar_usuario(db_session, dto, usuario_id=coordenador.id)

    resultado = await db_session.execute(select(AuditLog).where(AuditLog.entidade_id == usuario.id))
    log = resultado.scalar_one()
    assert log.entidade == "usuario"
    assert log.acao == "CRIAR"
    assert "senha" not in log.depois
    assert "senha_hash" not in log.depois


async def test_listar_usuarios_pagina_resultados(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-listar@tjr.app")
    for i in range(3):
        await criar_usuario(
            db_session,
            UsuarioCreate(
                nome=f"Arbitro {i}",
                email=f"arb-listar-{i}@tjr.app",
                senha="senha-forte",
                papel=Papel.ARBITRO,
            ),
            usuario_id=coordenador.id,
        )

    pagina1, total = await listar_usuarios(db_session, page=1, size=2)
    pagina2, _total2 = await listar_usuarios(db_session, page=2, size=2)

    assert total == 4  # coordenador + 3 arbitros
    assert len(pagina1) == 2
    assert len(pagina2) == 2
