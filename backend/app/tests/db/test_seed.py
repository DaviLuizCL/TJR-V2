from sqlalchemy import select

from app.core.security import verificar_senha
from app.db.seed import (
    EQUIPES_TJR,
    FICHA_VIAGEM_POR_NIVEL,
    FICHAS_TJR,
    MODALIDADES_TJR,
    seed_coordenador,
    seed_equipes,
    seed_equipes_credenciadas,
    seed_evento,
    seed_fichas,
    seed_inscricoes,
    seed_modalidades,
)
from app.models.criterio import Criterio
from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.inscricao import Inscricao
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


async def test_seed_fichas_cria_ficha_publicada_para_cada_modalidade_de_ficha_unica(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    por_nome = {m.nome: m for m in modalidades}
    for nome in FICHAS_TJR:
        resultado = await db_session.execute(
            select(Ficha).where(Ficha.modalidade_id == por_nome[nome].id)
        )
        fichas_da_modalidade = resultado.scalars().all()
        assert len(fichas_da_modalidade) == 1
        assert fichas_da_modalidade[0].nivel is None
        assert fichas_da_modalidade[0].status == FichaStatus.PUBLICADA


async def test_seed_fichas_cria_uma_ficha_por_nivel_para_viagem_ao_centro_da_terra(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == viagem.id))
    fichas_por_nivel = {f.nivel: f for f in resultado.scalars().all()}

    assert set(fichas_por_nivel) == set(FICHA_VIAGEM_POR_NIVEL)
    for ficha in fichas_por_nivel.values():
        assert ficha.status == FichaStatus.PUBLICADA


async def test_seed_fichas_cria_grupos_e_criterios_da_especificacao(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    danca = next(m for m in modalidades if m.nome == "Dança")
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == danca.id))
    ficha = resultado.scalar_one()

    resultado_grupos = await db_session.execute(select(Grupo).where(Grupo.ficha_id == ficha.id))
    grupos = resultado_grupos.scalars().all()
    assert len(grupos) == len(FICHAS_TJR["Dança"])

    resultado_criterios = await db_session.execute(
        select(Criterio).where(Criterio.grupo_id.in_([g.id for g in grupos]))
    )
    criterios = resultado_criterios.scalars().all()
    total_esperado = sum(len(criterios_spec) for _, criterios_spec in FICHAS_TJR["Dança"])
    assert len(criterios) == total_esperado


async def test_seed_fichas_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)
    await db_session.flush()
    await seed_fichas(db_session, modalidades)
    await db_session.flush()

    sumo = next(m for m in modalidades if m.nome == "Sumô")
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == sumo.id))
    assert len(resultado.scalars().all()) == 1


async def test_seed_equipes_credenciadas_cria_quatro_por_nivel(db_session):
    equipes = await seed_equipes_credenciadas(db_session)

    assert len(equipes) == len(EQUIPES_TJR)
    for nivel in (1, 2, 3, 4):
        do_nivel = [e for e in equipes if e.nivel == nivel]
        assert len(do_nivel) == 4


async def test_seed_equipes_credenciadas_e_idempotente(db_session):
    await seed_equipes_credenciadas(db_session)
    await db_session.flush()
    await seed_equipes_credenciadas(db_session)
    await db_session.flush()

    resultado = await db_session.execute(select(Equipe).where(Equipe.nome.like("Nível%")))
    assert len(resultado.scalars().all()) == len(EQUIPES_TJR)


async def test_seed_inscricoes_credencia_toda_equipe_em_toda_modalidade_do_seu_nivel(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)

    inscricoes = await seed_inscricoes(db_session, modalidades, equipes)

    assert len(inscricoes) == len(modalidades) * len(equipes)


async def test_seed_inscricoes_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)

    await seed_inscricoes(db_session, modalidades, equipes)
    await db_session.flush()
    await seed_inscricoes(db_session, modalidades, equipes)
    await db_session.flush()

    resultado = await db_session.execute(select(Inscricao))
    assert len(resultado.scalars().all()) == len(modalidades) * len(equipes)
