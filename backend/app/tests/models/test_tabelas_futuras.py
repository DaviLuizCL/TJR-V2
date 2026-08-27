import uuid
from datetime import date
from decimal import Decimal

from app.core.security import hash_senha
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.grupo import Grupo
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario


async def _criar_equipe(db_session, nome="Equipe A", nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    return equipe


async def test_equipe_nao_depende_de_um_evento_especifico(db_session):
    equipe = await _criar_equipe(db_session)

    assert not hasattr(equipe, "evento_id")


async def test_criar_equipe_e_inscricao_em_modalidade(db_session, modalidade):
    equipe = await _criar_equipe(db_session)

    inscricao = Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id)
    db_session.add(inscricao)
    await db_session.flush()

    assert inscricao.id is not None
    assert inscricao.equipe_id == equipe.id
    assert inscricao.modalidade_id == modalidade.id


async def test_mesma_equipe_pode_se_inscrever_em_modalidades_de_eventos_diferentes(
    db_session, modalidade
):
    equipe = await _criar_equipe(db_session)

    db_session.add(Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id))
    await db_session.flush()

    outro_evento = Evento(
        nome="TJR 2027",
        ano=2027,
        data_inicio=date(2027, 3, 10),
        data_fim=date(2027, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(outro_evento)
    await db_session.flush()

    outra_modalidade = Modalidade(
        evento_id=outro_evento.id,
        nome="Modalidade Outro Ano",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(outra_modalidade)
    await db_session.flush()

    db_session.add(Inscricao(equipe_id=equipe.id, modalidade_id=outra_modalidade.id))
    await db_session.flush()

    assert equipe.id is not None


async def test_criar_partida_entre_duas_equipes(db_session, modalidade):
    equipe_a = await _criar_equipe(db_session, nome="Equipe A")
    equipe_b = await _criar_equipe(db_session, nome="Equipe B")

    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()

    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipe_a.id,
        equipe_b_id=equipe_b.id,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    assert partida.equipe_a_id == equipe_a.id
    assert partida.equipe_b_id == equipe_b.id


async def test_lancamento_nasce_com_client_operation_id_revision_e_status(
    db_session, modalidade, ficha
):
    equipe = await _criar_equipe(db_session)
    arbitro = Usuario(
        nome="Arbitro Teste",
        email="arbitro@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.ARBITRO,
    )
    db_session.add(arbitro)
    await db_session.flush()

    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()

    operacao_id = uuid.uuid4()
    lancamento = Lancamento(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        arbitro_id=arbitro.id,
        client_operation_id=operacao_id,
        revision=1,
        status=LancamentoStatus.PENDENTE,
        total=Decimal("0"),
    )
    db_session.add(lancamento)
    await db_session.flush()

    assert lancamento.client_operation_id == operacao_id
    assert lancamento.revision == 1
    assert lancamento.status == LancamentoStatus.PENDENTE
    assert lancamento.ficha_id == ficha.id


async def test_lancamento_item_guarda_criterio_snapshot(db_session, modalidade, ficha):
    grupo = Grupo(ficha_id=ficha.id, nome="Parte Tecnica", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()

    equipe = await _criar_equipe(db_session)
    arbitro = Usuario(
        nome="Arbitro Item",
        email="arbitro-item@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.ARBITRO,
    )
    db_session.add(arbitro)
    await db_session.flush()

    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()

    lancamento = Lancamento(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        arbitro_id=arbitro.id,
        client_operation_id=uuid.uuid4(),
        revision=1,
        status=LancamentoStatus.PENDENTE,
        total=Decimal("0"),
    )
    db_session.add(lancamento)
    await db_session.flush()

    item = LancamentoItem(
        lancamento_id=lancamento.id,
        criterio_id=criterio.id,
        criterio_snapshot={"nome": "Lombada", "tipo": "CONTADOR", "pontos": "10"},
        ocorrencias=3,
        pontos=Decimal("30"),
    )
    db_session.add(item)
    await db_session.flush()

    assert item.criterio_snapshot["nome"] == "Lombada"
    assert item.pontos == Decimal("30")
