import uuid
from datetime import date

from app.core.security import hash_senha
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
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
from app.services.checklist import gerar_checklist


async def _evento(db):
    evento = Evento(
        nome="TJR",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db.add(evento)
    await db.flush()
    return evento


async def _modalidade(db, evento, *, tipo=TipoDisputa.INDIVIDUAL, qtd_rodadas=2, nome="Dança"):
    modalidade = Modalidade(
        evento_id=evento.id,
        nome=nome,
        tipo_disputa=tipo,
        niveis_aplicaveis=[1, 2, 3],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=qtd_rodadas,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db.add(modalidade)
    await db.flush()
    return modalidade


async def _inscrever(db, modalidade, nome, nivel=2, presente=True, ordem=None):
    equipe = Equipe(nome=nome, nivel=nivel, presente=presente)
    db.add(equipe)
    await db.flush()
    db.add(Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id, ordem_apresentacao=ordem))
    await db.flush()
    return equipe


async def _ficha(db, modalidade, nivel, status=FichaStatus.PUBLICADA):
    ficha = Ficha(modalidade_id=modalidade.id, nivel=nivel, versao=1, status=status)
    db.add(ficha)
    await db.flush()
    return ficha


async def _rodada(db, modalidade, numero):
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=numero,
        modo_horario=ModoHorario.MANUAL,
        status=RodadaStatus.AGENDADA,
    )
    db.add(rodada)
    await db.flush()
    return rodada


async def _arbitro(db, email, ativo=True):
    usuario = Usuario(
        nome="Juiz",
        email=email,
        senha_hash=hash_senha("senha-123"),
        papel=Papel.ARBITRO,
        ativo=ativo,
    )
    db.add(usuario)
    await db.flush()
    return usuario


def _item(secao, codigo):
    return next(i for i in secao.itens if i.codigo == codigo)


async def _secao_da(db, evento, modalidade):
    checklist = await gerar_checklist(db, evento.id)
    return next(m for m in checklist.modalidades if m.modalidade_id == modalidade.id)


async def test_ficha_ok_quando_todo_nivel_com_equipe_tem_ficha_publicada(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "A", nivel=2)
    await _ficha(db_session, modalidade, 2)

    secao = await _secao_da(db_session, evento, modalidade)

    assert _item(secao, "FICHA").ok is True


async def test_ficha_unica_entre_niveis_vale_pra_todos_os_niveis(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "A", nivel=2)
    await _inscrever(db_session, modalidade, "B", nivel=3)
    await _ficha(db_session, modalidade, None)

    secao = await _secao_da(db_session, evento, modalidade)

    assert _item(secao, "FICHA").ok is True


async def test_ficha_pendente_aponta_o_nivel_sem_ficha_publicada(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "A", nivel=2)
    await _inscrever(db_session, modalidade, "B", nivel=3)
    await _ficha(db_session, modalidade, 2)
    await _ficha(db_session, modalidade, 3, status=FichaStatus.RASCUNHO)

    item = _item(await _secao_da(db_session, evento, modalidade), "FICHA")

    assert item.ok is False
    assert "Nível 3" in item.mensagem


async def test_equipes_sem_inscricao_fica_pendente(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)

    item = _item(await _secao_da(db_session, evento, modalidade), "EQUIPES")

    assert item.ok is False


async def test_equipes_mostra_quantas_estao_ausentes(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "A")
    await _inscrever(db_session, modalidade, "B", presente=False)

    item = _item(await _secao_da(db_session, evento, modalidade), "EQUIPES")

    assert item.ok is True
    assert "2 equipes inscritas" in item.mensagem
    assert "1 ausente" in item.mensagem


async def test_rodadas_individual_pendente_quando_faltam_rodadas(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento, qtd_rodadas=2)
    await _rodada(db_session, modalidade, 1)

    item = _item(await _secao_da(db_session, evento, modalidade), "RODADAS")

    assert item.ok is False
    assert "1 de 2" in item.mensagem


async def test_rodadas_individual_ok_com_todas_criadas(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento, qtd_rodadas=2)
    await _rodada(db_session, modalidade, 1)
    await _rodada(db_session, modalidade, 2)

    item = _item(await _secao_da(db_session, evento, modalidade), "RODADAS")

    assert item.ok is True


async def test_ordem_pendente_aponta_nivel_sem_sorteio(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "A", nivel=1, ordem=1)
    await _inscrever(db_session, modalidade, "B", nivel=2, ordem=None)

    item = _item(await _secao_da(db_session, evento, modalidade), "ORDEM")

    assert item.ok is False
    assert "Nível 2" in item.mensagem
    assert "ABSOLUTO" not in item.mensagem


async def test_ordem_ok_quando_todo_nivel_foi_sorteado(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    await _inscrever(db_session, modalidade, "A", nivel=2, ordem=1)

    item = _item(await _secao_da(db_session, evento, modalidade), "ORDEM")

    assert item.ok is True


async def test_confronto_nao_tem_itens_de_rodada_nem_ordem(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento, tipo=TipoDisputa.CONFRONTO)

    secao = await _secao_da(db_session, evento, modalidade)

    codigos = {i.codigo for i in secao.itens}
    assert "RODADAS" not in codigos
    assert "ORDEM" not in codigos
    assert "CONFRONTOS" in codigos


async def test_confrontos_pendente_aponta_nivel_com_equipe_mas_sem_partida(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento, tipo=TipoDisputa.CONFRONTO)
    a = await _inscrever(db_session, modalidade, "A", nivel=2)
    b = await _inscrever(db_session, modalidade, "B", nivel=2)
    await _inscrever(db_session, modalidade, "C", nivel=3)
    rodada = await _rodada(db_session, modalidade, 1)
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=a.id,
            equipe_b_id=b.id,
            nivel=2,
            status=PartidaStatus.AGENDADA,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
        )
    )
    await db_session.flush()

    item = _item(await _secao_da(db_session, evento, modalidade), "CONFRONTOS")

    assert item.ok is False
    assert "Nível 3" in item.mensagem
    assert "Nível 2" not in item.mensagem


async def test_juizes_conta_so_arbitros_ativos(db_session):
    evento = await _evento(db_session)
    await _arbitro(db_session, f"juiz-{uuid.uuid4()}@tjr.app")
    await _arbitro(db_session, f"juiz-{uuid.uuid4()}@tjr.app", ativo=False)

    checklist = await gerar_checklist(db_session, evento.id)
    item = next(i for i in checklist.gerais if i.codigo == "JUIZES")

    assert item.ok is True
    assert "1 juiz" in item.mensagem


async def test_notas_pendentes_de_confirmacao_aparecem_no_geral(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    equipe = await _inscrever(db_session, modalidade, "A")
    ficha = await _ficha(db_session, modalidade, 2)
    rodada = await _rodada(db_session, modalidade, 1)
    arbitro = await _arbitro(db_session, f"juiz-{uuid.uuid4()}@tjr.app")
    db_session.add(
        Lancamento(
            ficha_id=ficha.id,
            rodada_id=rodada.id,
            tentativa=1,
            equipe_id=equipe.id,
            arbitro_id=arbitro.id,
            client_operation_id=uuid.uuid4(),
            status=LancamentoStatus.PENDENTE,
            total=0,
        )
    )
    await db_session.flush()

    checklist = await gerar_checklist(db_session, evento.id)
    item = next(i for i in checklist.gerais if i.codigo == "NOTAS_PENDENTES")

    assert item.ok is False
    assert "1 nota" in item.mensagem
