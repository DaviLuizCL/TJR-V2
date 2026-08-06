from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partida import Partida


async def listar_partidas_por_rodada(db: AsyncSession, rodada_id: UUID) -> list[Partida]:
    resultado = await db.execute(
        select(Partida).where(Partida.rodada_id == rodada_id).order_by(Partida.criado_em)
    )
    return list(resultado.scalars().all())
