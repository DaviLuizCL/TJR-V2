from app.core.security import hash_senha
from app.models.usuario import Papel, Usuario
from app.services.audit import registrar_audit_log


async def _criar_usuario(db_session) -> Usuario:
    usuario = Usuario(
        nome="Coordenador Audit",
        email="audit-service@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def test_registrar_audit_log_grava_entidade_e_acao(db_session):
    usuario = await _criar_usuario(db_session)

    log = await registrar_audit_log(
        db_session,
        usuario_id=usuario.id,
        entidade="evento",
        entidade_id=usuario.id,
        acao="CRIAR",
        antes=None,
        depois={"nome": "TJR 2026"},
    )

    assert log.id is not None
    assert log.usuario_id == usuario.id
    assert log.entidade == "evento"
    assert log.acao == "CRIAR"
    assert log.antes is None
    assert log.depois == {"nome": "TJR 2026"}


async def test_registrar_audit_log_aceita_justificativa_opcional(db_session):
    usuario = await _criar_usuario(db_session)

    log = await registrar_audit_log(
        db_session,
        usuario_id=usuario.id,
        entidade="modalidade",
        entidade_id=usuario.id,
        acao="ATUALIZAR",
        antes={"nome": "Antigo"},
        depois={"nome": "Novo"},
        justificativa="Corrigido nome digitado errado",
    )

    assert log.justificativa == "Corrigido nome digitado errado"
