import pytest
from sqlalchemy.exc import IntegrityError

from app.models.chave import Chave, ChaveEquipe
from app.models.equipe import Equipe
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus


async def test_criar_chave_com_nome_e_nivel(db_session, modalidade):
    chave = Chave(modalidade_id=modalidade.id, nivel=1, nome="Chave A")
    db_session.add(chave)
    await db_session.flush()

    assert chave.id is not None
    assert chave.nome == "Chave A"
    assert chave.nivel == 1


async def test_associar_equipe_a_chave(db_session, modalidade):
    chave = Chave(modalidade_id=modalidade.id, nivel=1, nome="Chave A")
    db_session.add(chave)
    await db_session.flush()
    equipe = Equipe(nome="Equipe 1", nivel=1)
    db_session.add(equipe)
    await db_session.flush()

    vinculo = ChaveEquipe(chave_id=chave.id, equipe_id=equipe.id)
    db_session.add(vinculo)
    await db_session.flush()

    assert vinculo.id is not None


async def test_chave_equipe_rejeita_par_duplicado(db_session, modalidade):
    chave = Chave(modalidade_id=modalidade.id, nivel=1, nome="Chave A")
    db_session.add(chave)
    await db_session.flush()
    equipe = Equipe(nome="Equipe 1", nivel=1)
    db_session.add(equipe)
    await db_session.flush()

    db_session.add(ChaveEquipe(chave_id=chave.id, equipe_id=equipe.id))
    await db_session.flush()
    db_session.add(ChaveEquipe(chave_id=chave.id, equipe_id=equipe.id))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_partida_sem_chave_id_e_partida_de_mata_mata_normal(db_session, modalidade):
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    equipe_a = Equipe(nome="Equipe A", nivel=1)
    equipe_b = Equipe(nome="Equipe B", nivel=1)
    db_session.add_all([equipe_a, equipe_b])
    await db_session.flush()

    from app.models.modalidade import FormatoChaveamento

    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipe_a.id,
        equipe_b_id=equipe_b.id,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()
    await db_session.refresh(partida)

    assert partida.chave_id is None


async def test_partida_de_fase_de_grupos_carrega_chave_id(db_session, modalidade):
    chave = Chave(modalidade_id=modalidade.id, nivel=1, nome="Chave A")
    db_session.add(chave)
    await db_session.flush()
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    equipe_a = Equipe(nome="Equipe A", nivel=1)
    equipe_b = Equipe(nome="Equipe B", nivel=1)
    db_session.add_all([equipe_a, equipe_b])
    await db_session.flush()

    from app.models.modalidade import FormatoChaveamento

    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipe_a.id,
        equipe_b_id=equipe_b.id,
        chave_id=chave.id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()
    await db_session.refresh(partida)

    assert partida.chave_id == chave.id
