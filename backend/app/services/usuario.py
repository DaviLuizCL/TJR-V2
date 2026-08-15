from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate
from app.services.audit import registrar_audit_log


def _serializar(usuario: Usuario) -> dict:
    return {"nome": usuario.nome, "email": usuario.email, "papel": usuario.papel.value}


async def criar_usuario(db: AsyncSession, dto: UsuarioCreate, *, usuario_id: UUID) -> Usuario:
    existente = await db.scalar(select(Usuario).where(Usuario.email == dto.email))
    if existente is not None:
        raise AppError(
            codigo="EMAIL_JA_CADASTRADO",
            mensagem="Ja existe um usuario com este email.",
            status_code=409,
        )

    usuario = Usuario(
        nome=dto.nome,
        email=dto.email,
        senha_hash=hash_senha(dto.senha),
        papel=dto.papel,
    )
    db.add(usuario)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="usuario",
        entidade_id=usuario.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(usuario),
    )
    return usuario


async def listar_usuarios(db: AsyncSession, *, page: int, size: int) -> tuple[list[Usuario], int]:
    total = await db.scalar(select(func.count()).select_from(Usuario))
    resultado = await db.execute(
        select(Usuario).order_by(Usuario.nome).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0
