from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.usuario import Papel, Usuario


async def test_criar_audit_log_com_antes_e_depois(db_session):
    usuario = Usuario(
        nome="Coordenador Audit",
        email="audit@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()

    log = AuditLog(
        usuario_id=usuario.id,
        entidade="modalidade",
        entidade_id=usuario.id,
        acao="CRIAR",
        justificativa=None,
        antes=None,
        depois={"nome": "Sumo de Robos"},
    )
    db_session.add(log)
    await db_session.flush()

    assert log.id is not None
    assert log.antes is None
    assert log.depois == {"nome": "Sumo de Robos"}
    assert log.criado_em is not None
