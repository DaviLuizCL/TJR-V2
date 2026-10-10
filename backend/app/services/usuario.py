from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.usuario import Papel, Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
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


async def obter_usuario(db: AsyncSession, usuario_alvo_id: UUID) -> Usuario:
    usuario = await db.get(Usuario, usuario_alvo_id)
    if usuario is None:
        raise AppError(
            codigo="USUARIO_NAO_ENCONTRADO", mensagem="Usuario nao encontrado.", status_code=404
        )
    return usuario


def _serializar_completo(usuario: Usuario) -> dict:
    return {**_serializar(usuario), "ativo": usuario.ativo}


async def atualizar_usuario(
    db: AsyncSession, usuario_alvo_id: UUID, dto: UsuarioUpdate, *, usuario_id: UUID
) -> Usuario:
    usuario = await obter_usuario(db, usuario_alvo_id)
    mudancas = dto.model_dump(exclude_unset=True, exclude_none=True)

    # Ninguem se tranca pra fora: o coordenador logado nao pode se desativar
    # nem deixar de ser coordenador (senao pode sobrar nenhum coordenador).
    if usuario.id == usuario_id and (
        mudancas.get("ativo") is False
        or ("papel" in mudancas and mudancas["papel"] != Papel.COORDENADOR)
    ):
        raise AppError(
            codigo="NAO_PODE_ALTERAR_PROPRIO_ACESSO",
            mensagem="Voce nao pode desativar a propria conta nem tirar seu proprio acesso de "
            "coordenador. Peca para outro coordenador fazer isso.",
            status_code=422,
        )

    antes = _serializar_completo(usuario)
    for campo, valor in mudancas.items():
        setattr(usuario, campo, valor)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="usuario",
        entidade_id=usuario.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar_completo(usuario),
    )
    return usuario


async def definir_senha(
    db: AsyncSession, usuario_alvo_id: UUID, senha: str, *, usuario_id: UUID
) -> Usuario:
    usuario = await obter_usuario(db, usuario_alvo_id)
    usuario.senha_hash = hash_senha(senha)
    await db.flush()

    # Nunca grava a senha (nem o hash) no rastro, so que ela foi trocada.
    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="usuario",
        entidade_id=usuario.id,
        acao="TROCAR_SENHA",
        antes=None,
        depois=_serializar(usuario),
    )
    return usuario
