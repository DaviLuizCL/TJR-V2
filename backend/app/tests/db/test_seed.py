from sqlalchemy import select

from app.core.security import verificar_senha
from app.db.seed import seed_coordenador, seed_equipes
from app.models.equipe import Equipe
from app.models.usuario import Papel, Usuario


async def test_seed_coordenador_cria_usuario_coordenador(db_session):
    await seed_coordenador(db_session, email="novo-coord@tjr.app", senha="senha-123")
    await db_session.flush()

    resultado = await db_session.execute(
        select(Usuario).where(Usuario.email == "novo-coord@tjr.app")
    )
    usuario = resultado.scalar_one()

    assert usuario.papel == Papel.COORDENADOR
    assert usuario.ativo is True
    assert verificar_senha("senha-123", usuario.senha_hash)


async def test_seed_coordenador_e_idempotente(db_session):
    await seed_coordenador(db_session, email="repetido@tjr.app", senha="senha-123")
    await seed_coordenador(db_session, email="repetido@tjr.app", senha="outra-senha")
    await db_session.flush()

    resultado = await db_session.execute(select(Usuario).where(Usuario.email == "repetido@tjr.app"))
    usuarios = resultado.scalars().all()

    assert len(usuarios) == 1


async def test_seed_equipes_cria_dez_por_nivel(db_session):
    equipes = await seed_equipes(db_session, por_nivel=10)
    await db_session.flush()

    assert len(equipes) == 40
    for nivel in (1, 2, 3, 4):
        do_nivel = [e for e in equipes if e.nivel == nivel]
        assert len(do_nivel) == 10


async def test_seed_equipes_nome_contem_nome_e_nivel(db_session):
    equipes = await seed_equipes(db_session, por_nivel=10)

    for equipe in equipes:
        assert str(equipe.nivel) in equipe.nome
        assert "Equipe" in equipe.nome


async def test_seed_equipes_e_idempotente(db_session):
    await seed_equipes(db_session, por_nivel=10)
    await db_session.flush()
    await seed_equipes(db_session, por_nivel=10)
    await db_session.flush()

    resultado = await db_session.execute(select(Equipe))
    equipes = resultado.scalars().all()

    assert len(equipes) == 40
