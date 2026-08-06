from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.criterio import Criterio
from app.models.grupo import Grupo
from app.schemas.grupo import GrupoCreate, GrupoUpdate
from app.services.audit import registrar_audit_log
from app.services.ficha import obter_ficha


def _serializar(grupo: Grupo) -> dict:
    return {"ficha_id": str(grupo.ficha_id), "nome": grupo.nome, "ordem": grupo.ordem}


async def obter_grupo(db: AsyncSession, grupo_id: UUID) -> Grupo:
    grupo = await db.get(Grupo, grupo_id)
    if grupo is None:
        raise AppError(
            codigo="GRUPO_NAO_ENCONTRADO", mensagem="Grupo nao encontrado.", status_code=404
        )
    return grupo


async def criar_grupo(
    db: AsyncSession, ficha_id: UUID, dto: GrupoCreate, *, usuario_id: UUID
) -> Grupo:
    # Grupo e so organizacao visual da ficha: nao faz parte do contrato de
    # pontuacao (o criterio_snapshot do lancamento referencia apenas o
    # criterio, nunca o grupo), entao mexer nele nunca versiona a ficha,
    # mesmo com ela PUBLICADA.
    await obter_ficha(db, ficha_id)

    grupo = Grupo(ficha_id=ficha_id, nome=dto.nome, ordem=dto.ordem)
    db.add(grupo)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="grupo",
        entidade_id=grupo.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(grupo),
    )
    return grupo


async def atualizar_grupo(
    db: AsyncSession, grupo_id: UUID, dto: GrupoUpdate, *, usuario_id: UUID
) -> Grupo:
    grupo = await obter_grupo(db, grupo_id)

    antes = _serializar(grupo)
    dados = dto.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(grupo, campo, valor)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="grupo",
        entidade_id=grupo.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(grupo),
    )
    return grupo


async def deletar_grupo(db: AsyncSession, grupo_id: UUID, *, usuario_id: UUID) -> None:
    grupo = await obter_grupo(db, grupo_id)
    antes = _serializar(grupo)

    resultado = await db.execute(select(Criterio).where(Criterio.grupo_id == grupo.id))
    for criterio in resultado.scalars().all():
        await db.delete(criterio)

    await db.delete(grupo)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="grupo",
        entidade_id=grupo.id,
        acao="DELETAR",
        antes=antes,
        depois=None,
    )
