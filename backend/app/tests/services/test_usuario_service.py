import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha, verificar_senha
from app.models.audit_log import AuditLog
from app.models.usuario import Papel, Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.services.usuario import (
    atualizar_usuario,
    criar_usuario,
    definir_senha,
    listar_usuarios,
)


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


async def test_criar_usuario_com_email_duplicado_ignorando_case_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    await criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Arbitro Um", email="case-dup@tjr.app", senha="senha-forte", papel=Papel.ARBITRO
        ),
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await criar_usuario(
            db_session,
            UsuarioCreate(
                nome="Arbitro Dois",
                email="Case-Dup@Tjr.App",
                senha="senha-forte",
                papel=Papel.ARBITRO,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "EMAIL_JA_CADASTRADO"


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


async def _criar_arbitro(db_session, email="juiz-edit@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Juiz", email=email, senha_hash=hash_senha("senha-antiga"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def test_atualizar_usuario_desativa_a_conta(db_session):
    coordenador = await _criar_coordenador(db_session)
    juiz = await _criar_arbitro(db_session)

    atualizado = await atualizar_usuario(
        db_session, juiz.id, UsuarioUpdate(ativo=False), usuario_id=coordenador.id
    )

    assert atualizado.ativo is False


async def test_atualizar_usuario_troca_papel_e_nome(db_session):
    coordenador = await _criar_coordenador(db_session)
    juiz = await _criar_arbitro(db_session)

    atualizado = await atualizar_usuario(
        db_session,
        juiz.id,
        UsuarioUpdate(nome="Juíza Ana", papel=Papel.SECRETARIA),
        usuario_id=coordenador.id,
    )

    assert atualizado.nome == "Juíza Ana"
    assert atualizado.papel == Papel.SECRETARIA


async def test_atualizar_usuario_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    juiz = await _criar_arbitro(db_session)

    await atualizar_usuario(
        db_session, juiz.id, UsuarioUpdate(ativo=False), usuario_id=coordenador.id
    )

    log = await db_session.scalar(
        select(AuditLog).where(AuditLog.entidade_id == juiz.id, AuditLog.acao == "ATUALIZAR")
    )
    assert log is not None


async def test_coordenador_nao_pode_se_desativar(db_session):
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as erro:
        await atualizar_usuario(
            db_session, coordenador.id, UsuarioUpdate(ativo=False), usuario_id=coordenador.id
        )
    assert erro.value.codigo == "NAO_PODE_ALTERAR_PROPRIO_ACESSO"


async def test_coordenador_nao_pode_tirar_o_proprio_papel_de_coordenador(db_session):
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as erro:
        await atualizar_usuario(
            db_session,
            coordenador.id,
            UsuarioUpdate(papel=Papel.ARBITRO),
            usuario_id=coordenador.id,
        )
    assert erro.value.codigo == "NAO_PODE_ALTERAR_PROPRIO_ACESSO"


async def test_coordenador_pode_mudar_o_proprio_nome(db_session):
    coordenador = await _criar_coordenador(db_session)

    atualizado = await atualizar_usuario(
        db_session, coordenador.id, UsuarioUpdate(nome="Coord Novo"), usuario_id=coordenador.id
    )

    assert atualizado.nome == "Coord Novo"


async def test_atualizar_usuario_inexistente_retorna_404(db_session):
    import uuid

    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as erro:
        await atualizar_usuario(
            db_session, uuid.uuid4(), UsuarioUpdate(ativo=False), usuario_id=coordenador.id
        )
    assert erro.value.status_code == 404


async def test_definir_senha_troca_a_senha_do_usuario(db_session):
    coordenador = await _criar_coordenador(db_session)
    juiz = await _criar_arbitro(db_session)

    await definir_senha(db_session, juiz.id, "senha-nova", usuario_id=coordenador.id)

    assert verificar_senha("senha-nova", juiz.senha_hash)
    assert not verificar_senha("senha-antiga", juiz.senha_hash)


async def test_definir_senha_grava_audit_log_sem_a_senha(db_session):
    coordenador = await _criar_coordenador(db_session)
    juiz = await _criar_arbitro(db_session)

    await definir_senha(db_session, juiz.id, "senha-nova", usuario_id=coordenador.id)

    log = await db_session.scalar(
        select(AuditLog).where(AuditLog.entidade_id == juiz.id, AuditLog.acao == "TROCAR_SENHA")
    )
    assert log is not None
    assert "senha-nova" not in str(log.antes) + str(log.depois)
