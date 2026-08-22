import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.core.security import hash_senha
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.partida import Partida
from app.models.usuario import Papel, Usuario
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.chaveamento import gerar_chaveamento_inicial
from app.services.ficha import publicar_ficha
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento
from app.services.relatorio import (
    agrupar_lancamentos_por_combate,
    descrever_resultado_combate,
    gerar_relatorio_auditoria_evento_pdf,
    gerar_relatorio_auditoria_pdf,
)


async def _criar_coordenador(db_session, email="coord-relatorio@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_arbitro(db_session, email="arbitro-relatorio@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Arbitro", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_evento(db_session, nome="TJR 2026") -> Evento:
    evento = Evento(
        nome=nome,
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    return evento


async def _criar_modalidade_confronto(
    db_session, evento: Evento | None = None, nome: str = "Sumo de Robos"
) -> Modalidade:
    if evento is None:
        evento = await _criar_evento(db_session)

    modalidade = Modalidade(
        evento_id=evento.id,
        nome=nome,
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=3,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever_equipes(db_session, modalidade, coordenador, qtd) -> list[Equipe]:
    equipes = []
    for i in range(qtd):
        equipe = Equipe(nome=f"Equipe {i + 1}", nivel=1)
        db_session.add(equipe)
        await db_session.flush()
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )
        equipes.append(equipe)
    return equipes


async def _criar_ficha_com_criterio(db_session, modalidade, coordenador) -> tuple[Ficha, Criterio]:
    ficha = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(ficha)
    await db_session.flush()
    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Ataque",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    return ficha, criterio


async def test_gerar_relatorio_auditoria_pdf_retorna_pdf_valido_com_lancamento(db_session):
    coordenador = await _criar_coordenador(db_session)
    arbitro = await _criar_arbitro(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
    partida = resultado.scalars().first()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipes[0].id,
        partida_id=partida.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=3)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    pdf_bytes = await gerar_relatorio_auditoria_pdf(db_session, modalidade.id)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


async def test_gerar_relatorio_auditoria_pdf_com_os_dois_lados_do_combate_lancados_nao_quebra(
    db_session,
):
    coordenador = await _criar_coordenador(db_session)
    arbitro = await _criar_arbitro(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)

    rodada = await gerar_chaveamento_inicial(db_session, modalidade.id, usuario_id=coordenador.id)
    resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
    partida = resultado.scalars().first()

    for equipe, ocorrencias in ((partida.equipe_a_id, 3), (partida.equipe_b_id, 1)):
        payload = LancamentoCreate(
            ficha_id=ficha.id,
            rodada_id=rodada.id,
            tentativa=1,
            equipe_id=equipe,
            partida_id=partida.id,
            client_operation_id=uuid.uuid4(),
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)],
        )
        lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
        await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    pdf_bytes = await gerar_relatorio_auditoria_pdf(db_session, modalidade.id)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


async def test_gerar_relatorio_auditoria_pdf_sem_nenhum_lancamento_nao_quebra(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    await _inscrever_equipes(db_session, modalidade, coordenador, 2)

    pdf_bytes = await gerar_relatorio_auditoria_pdf(db_session, modalidade.id)

    assert pdf_bytes.startswith(b"%PDF")


async def test_gerar_relatorio_auditoria_evento_pdf_junta_todas_as_modalidades(db_session):
    coordenador = await _criar_coordenador(db_session)
    arbitro = await _criar_arbitro(db_session)
    evento = await _criar_evento(db_session)
    modalidade_a = await _criar_modalidade_confronto(db_session, evento, nome="Sumo de Robos")
    modalidade_b = await _criar_modalidade_confronto(db_session, evento, nome="Cabo de Guerra")
    equipes_a = await _inscrever_equipes(db_session, modalidade_a, coordenador, 4)
    await _inscrever_equipes(db_session, modalidade_b, coordenador, 2)
    ficha_a, criterio_a = await _criar_ficha_com_criterio(db_session, modalidade_a, coordenador)

    rodada_a = await gerar_chaveamento_inicial(
        db_session, modalidade_a.id, usuario_id=coordenador.id
    )
    resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada_a.id))
    partida_a = resultado.scalars().first()
    payload = LancamentoCreate(
        ficha_id=ficha_a.id,
        rodada_id=rodada_a.id,
        tentativa=1,
        equipe_id=equipes_a[0].id,
        partida_id=partida_a.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio_a.id, ocorrencias=3)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    pdf_evento = await gerar_relatorio_auditoria_evento_pdf(db_session, evento.id)
    pdf_so_modalidade_a = await gerar_relatorio_auditoria_pdf(db_session, modalidade_a.id)

    assert pdf_evento.startswith(b"%PDF")
    # O relatorio do evento inclui as duas modalidades, entao tem que ser
    # maior que o relatorio de uma unica modalidade sozinha.
    assert len(pdf_evento) > len(pdf_so_modalidade_a)


async def test_gerar_relatorio_auditoria_evento_pdf_sem_modalidade_nenhuma_nao_quebra(db_session):
    evento = await _criar_evento(db_session, nome="Evento Vazio")

    pdf_bytes = await gerar_relatorio_auditoria_evento_pdf(db_session, evento.id)

    assert pdf_bytes.startswith(b"%PDF")


def _linha(*, partida_id=None, tentativa=1):
    lancamento = SimpleNamespace(partida_id=partida_id, tentativa=tentativa)
    return (lancamento, None, None, None)


def test_agrupar_lancamentos_por_combate_agrupa_mesma_partida_e_tentativa():
    partida_id = uuid.uuid4()
    linha_a = _linha(partida_id=partida_id, tentativa=1)
    linha_b = _linha(partida_id=partida_id, tentativa=1)

    grupos = agrupar_lancamentos_por_combate([linha_a, linha_b])

    assert grupos == [[linha_a, linha_b]]


def test_agrupar_lancamentos_por_combate_nao_agrupa_tentativas_diferentes_da_mesma_partida():
    partida_id = uuid.uuid4()
    linha_1 = _linha(partida_id=partida_id, tentativa=1)
    linha_2 = _linha(partida_id=partida_id, tentativa=2)

    grupos = agrupar_lancamentos_por_combate([linha_1, linha_2])

    assert grupos == [[linha_1], [linha_2]]


def test_agrupar_lancamentos_por_combate_mantem_lancamento_individual_sozinho():
    linha = _linha(partida_id=None, tentativa=1)

    grupos = agrupar_lancamentos_por_combate([linha])

    assert grupos == [[linha]]


def test_agrupar_lancamentos_por_combate_preserva_ordem_de_chegada():
    partida_a = uuid.uuid4()
    partida_b = uuid.uuid4()
    linha_individual = _linha(partida_id=None)
    linha_a1 = _linha(partida_id=partida_a, tentativa=1)
    linha_b1 = _linha(partida_id=partida_b, tentativa=1)
    linha_a2 = _linha(partida_id=partida_a, tentativa=1)

    grupos = agrupar_lancamentos_por_combate([linha_individual, linha_a1, linha_b1, linha_a2])

    assert grupos == [[linha_individual], [linha_a1, linha_a2], [linha_b1]]


def test_descrever_resultado_combate_indica_vencedor_pelo_maior_total():
    descricao = descrever_resultado_combate("Equipe A", 10, "Equipe B", 4)

    assert descricao == "Equipe A 10 x 4 Equipe B — Vencedor: Equipe A"


def test_descrever_resultado_combate_indica_vencedor_do_outro_lado():
    descricao = descrever_resultado_combate("Equipe A", 2, "Equipe B", 9)

    assert "Vencedor: Equipe B" in descricao


def test_descrever_resultado_combate_indica_empate():
    descricao = descrever_resultado_combate("Equipe A", 5, "Equipe B", 5)

    assert "Empate" in descricao
    assert "Vencedor" not in descricao
