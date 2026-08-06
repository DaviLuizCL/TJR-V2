import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_senha
from app.db.session import AsyncSessionLocal
from app.models.equipe import Equipe
from app.models.usuario import Papel, Usuario


async def seed_coordenador(db: AsyncSession, *, email: str, senha: str) -> Usuario:
    resultado = await db.execute(select(Usuario).where(Usuario.email == email))
    usuario = resultado.scalar_one_or_none()
    if usuario is not None:
        return usuario

    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha(senha),
        papel=Papel.COORDENADOR,
        ativo=True,
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def seed_equipes(db: AsyncSession, *, por_nivel: int = 10) -> list[Equipe]:
    equipes: list[Equipe] = []
    for nivel in (1, 2, 3, 4):
        for numero in range(1, por_nivel + 1):
            nome = f"Equipe {numero:02d} - Nivel {nivel}"
            resultado = await db.execute(select(Equipe).where(Equipe.nome == nome))
            equipe = resultado.scalar_one_or_none()
            if equipe is None:
                equipe = Equipe(nome=nome, nivel=nivel, ativo=True)
                db.add(equipe)
                await db.flush()
            equipes.append(equipe)
    return equipes


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_coordenador(
            db, email=settings.seed_coordenador_email, senha=settings.seed_coordenador_senha
        )
        await seed_equipes(db, por_nivel=10)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(_main())
