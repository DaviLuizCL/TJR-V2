from sqlalchemy import select

from app.core.security import verificar_senha
from app.db.seed import (
    MODALIDADES_TJR,
    seed_coordenador,
    seed_equipes,
    seed_evento,
    seed_modalidades,
)
from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.modalidade import Modalidade, ModalidadeStatus, TipoDisputa
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


async def test_seed_evento_cria_evento_tjr_2026(db_session):
    evento = await seed_evento(db_session)
    await db_session.flush()

    resultado = await db_session.execute(select(Evento).where(Evento.nome == "TJR 2026"))
    persistido = resultado.scalar_one()

    assert evento.id == persistido.id
    assert persistido.ano == 2026


async def test_seed_evento_e_idempotente(db_session):
    primeiro = await seed_evento(db_session)
    await db_session.flush()
    segundo = await seed_evento(db_session)
    await db_session.flush()

    resultado = await db_session.execute(select(Evento).where(Evento.nome == "TJR 2026"))
    eventos = resultado.scalars().all()

    assert len(eventos) == 1
    assert primeiro.id == segundo.id


async def test_seed_modalidades_cria_todas_as_modalidades_do_tjr(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await db_session.flush()

    assert len(modalidades) == len(MODALIDADES_TJR)
    nomes = {m.nome for m in modalidades}
    assert nomes == {spec["nome"] for spec in MODALIDADES_TJR}
    for modalidade in modalidades:
        assert modalidade.evento_id == evento.id
        assert modalidade.status == ModalidadeStatus.PUBLICADA
        assert modalidade.niveis_aplicaveis == [1, 2, 3, 4]


async def test_seed_modalidades_confronto_tem_formato_de_chaveamento(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    por_nome = {m.nome: m for m in modalidades}
    assert por_nome["Sumô"].tipo_disputa == TipoDisputa.CONFRONTO
    assert por_nome["Sumô"].formato_chaveamento is not None
    assert por_nome["Dança"].tipo_disputa == TipoDisputa.INDIVIDUAL
    assert por_nome["Dança"].formato_chaveamento is None


async def test_seed_modalidades_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    await seed_modalidades(db_session, evento)
    await db_session.flush()
    await seed_modalidades(db_session, evento)
    await db_session.flush()

    resultado = await db_session.execute(
        select(Modalidade).where(Modalidade.evento_id == evento.id)
    )
    modalidades = resultado.scalars().all()

    assert len(modalidades) == len(MODALIDADES_TJR)
