import uuid

from app.models.ficha import FichaStatus
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.modalidade import TipoDisputa
from app.services.publico import sequencia_publica_do_evento
from app.tests.services.test_checklist_service import (
    _arbitro,
    _evento,
    _ficha,
    _inscrever,
    _modalidade,
    _rodada,
)


async def _lancar(db, *, ficha, rodada, equipe, arbitro, tentativa=1, status=None):
    db.add(
        Lancamento(
            ficha_id=ficha.id,
            rodada_id=rodada.id,
            tentativa=tentativa,
            equipe_id=equipe.id,
            arbitro_id=arbitro.id,
            client_operation_id=uuid.uuid4(),
            status=status or LancamentoStatus.CONFIRMADO,
            total=0,
        )
    )
    await db.flush()


def _nomes(nivel):
    return [equipe.nome for equipe in nivel.equipes]


async def test_sequencia_publica_lista_so_modalidades_individuais_do_evento_por_nome(db_session):
    evento = await _evento(db_session)
    await _modalidade(db_session, evento, nome="Resgate no Plano")
    await _modalidade(db_session, evento, nome="Dança")
    await _modalidade(db_session, evento, nome="Sumô", tipo=TipoDisputa.CONFRONTO)

    sequencia = await sequencia_publica_do_evento(db_session, evento.id)

    assert [m.nome for m in sequencia] == ["Dança", "Resgate no Plano"]


async def test_sequencia_publica_segue_a_ordem_sorteada_separada_por_nivel(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "Beta", nivel=2, ordem=2)
    await _inscrever(db_session, modalidade, "Alfa", nivel=2, ordem=1)
    await _inscrever(db_session, modalidade, "Gama", nivel=3)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    assert [n.nivel for n in dados.niveis] == [2, 3]
    assert _nomes(dados.niveis[0]) == ["Alfa", "Beta"]
    assert [e.posicao for e in dados.niveis[0].equipes] == [1, 2]


async def test_sequencia_publica_esconde_equipe_desativada(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "Ativa")
    desativada = await _inscrever(db_session, modalidade, "Desativada")
    desativada.ativo = False
    await db_session.flush()

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    assert _nomes(dados.niveis[0]) == ["Ativa"]


async def test_sequencia_publica_marca_por_rodada_quem_ja_competiu(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada_1 = await _rodada(db_session, modalidade, 1)
    await _rodada(db_session, modalidade, 2)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    competiu = await _inscrever(db_session, modalidade, "Competiu", ordem=1)
    await _inscrever(db_session, modalidade, "Falta", ordem=2)
    await _lancar(db_session, ficha=ficha, rodada=rodada_1, equipe=competiu, arbitro=arbitro)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    assert dados.rodadas == [1, 2]
    competiu_out, falta_out = dados.niveis[0].equipes
    assert competiu_out.rodadas_competidas == [1]
    assert falta_out.rodadas_competidas == []


async def test_sequencia_publica_conta_lancamento_pendente_mas_nao_anulado(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada = await _rodada(db_session, modalidade, 1)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    pendente = await _inscrever(db_session, modalidade, "Pendente", ordem=1)
    anulada = await _inscrever(db_session, modalidade, "Anulada", ordem=2)
    await _lancar(
        db_session,
        ficha=ficha,
        rodada=rodada,
        equipe=pendente,
        arbitro=arbitro,
        status=LancamentoStatus.PENDENTE,
    )
    await _lancar(
        db_session,
        ficha=ficha,
        rodada=rodada,
        equipe=anulada,
        arbitro=arbitro,
        status=LancamentoStatus.ANULADO,
    )

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    pendente_out, anulada_out = dados.niveis[0].equipes
    assert pendente_out.rodadas_competidas == [1]
    assert anulada_out.rodadas_competidas == []


async def test_sequencia_publica_so_conta_rodada_com_todas_as_tentativas(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    modalidade.tentativas_por_rodada = 2
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada = await _rodada(db_session, modalidade, 1)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    equipe = await _inscrever(db_session, modalidade, "Meio caminho")
    await _lancar(db_session, ficha=ficha, rodada=rodada, equipe=equipe, arbitro=arbitro)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    assert dados.niveis[0].equipes[0].rodadas_competidas == []


async def test_sequencia_publica_aponta_a_proxima_presente_da_rodada_mais_atrasada(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada_1 = await _rodada(db_session, modalidade, 1)
    await _rodada(db_session, modalidade, 2)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    primeira = await _inscrever(db_session, modalidade, "Primeira", ordem=1)
    await _inscrever(db_session, modalidade, "Ausente", ordem=2, presente=False)
    await _inscrever(db_session, modalidade, "Terceira", ordem=3)
    await _lancar(db_session, ficha=ficha, rodada=rodada_1, equipe=primeira, arbitro=arbitro)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    assert [e.nome for e in dados.niveis[0].equipes if e.proxima] == ["Terceira"]
    assert dados.niveis[0].equipes[1].presente is False


async def test_sequencia_publica_sem_proxima_quando_todas_competiram(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada = await _rodada(db_session, modalidade, 1)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    equipe = await _inscrever(db_session, modalidade, "Unica")
    await _lancar(db_session, ficha=ficha, rodada=rodada, equipe=equipe, arbitro=arbitro)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    assert dados.niveis[0].equipes[0].proxima is False


async def test_sequencia_publica_conta_equipes_na_frente_pela_fila_de_quem_falta(db_session):
    # Fila igual a do Pontuar: rodada mais atrasada primeiro, depois a ordem.
    # Alfa ja fez a rodada 1, entao volta pro fim da fila (rodada 2).
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada_1 = await _rodada(db_session, modalidade, 1)
    await _rodada(db_session, modalidade, 2)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    alfa = await _inscrever(db_session, modalidade, "Alfa", ordem=1)
    await _inscrever(db_session, modalidade, "Beta", ordem=2, presente=False)
    await _inscrever(db_session, modalidade, "Gama", ordem=3)
    await _inscrever(db_session, modalidade, "Delta", ordem=4)
    await _lancar(db_session, ficha=ficha, rodada=rodada_1, equipe=alfa, arbitro=arbitro)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    na_frente = {e.nome: e.equipes_na_frente for e in dados.niveis[0].equipes}
    assert na_frente == {"Gama": 0, "Delta": 1, "Alfa": 2, "Beta": None}


async def test_sequencia_publica_sem_equipes_na_frente_pra_quem_ja_terminou(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    ficha = await _ficha(db_session, modalidade, 2, FichaStatus.PUBLICADA)
    rodada = await _rodada(db_session, modalidade, 1)
    arbitro = await _arbitro(db_session, "juiz-publico@tjr.app")
    terminou = await _inscrever(db_session, modalidade, "Terminou", ordem=1)
    await _inscrever(db_session, modalidade, "Falta", ordem=2)
    await _lancar(db_session, ficha=ficha, rodada=rodada, equipe=terminou, arbitro=arbitro)

    (dados,) = await sequencia_publica_do_evento(db_session, evento.id)

    terminou_out, falta_out = dados.niveis[0].equipes
    assert terminou_out.equipes_na_frente is None
    assert falta_out.equipes_na_frente == 0
