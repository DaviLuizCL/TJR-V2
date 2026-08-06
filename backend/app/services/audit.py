from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def registrar_audit_log(
    db: AsyncSession,
    *,
    usuario_id: UUID,
    entidade: str,
    entidade_id: UUID,
    acao: str,
    antes: dict | None = None,
    depois: dict | None = None,
    justificativa: str | None = None,
) -> AuditLog:
    log = AuditLog(
        usuario_id=usuario_id,
        entidade=entidade,
        entidade_id=entidade_id,
        acao=acao,
        justificativa=justificativa,
        antes=antes,
        depois=depois,
    )
    db.add(log)
    await db.flush()
    return log
