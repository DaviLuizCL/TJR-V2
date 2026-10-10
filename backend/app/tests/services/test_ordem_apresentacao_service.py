from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.inscricao import Inscricao
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.usuario import Papel, Usuario
from app.services.ordem_apresentacao import (
    definir_ordem,
    gerar_sequencia_pdf,
    listar_sequencia,
    sortear_ordem,
)


async def _criar_coordenador(db_session) -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email="coord-ordem@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(db_session, *, tipo=TipoDisputa.INDIVIDUAL) -> Modalidade:
    evento = Evento(
        nome="TJR 2026",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    modalidade = Modalidade(
        evento_id=evento.id,
        nome="Dança",
        tipo_disputa=tipo,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever(db_session, modalidade, nome, nivel=1, ativo=True, presente=True) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel, ativo=ativo, presente=presente)
    db_session.add(equipe)
    await db_session.flush()
    db_session.add(Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id))
    await db_session.flush()
    return equipe


async def _ordem_por_equipe(db_session, modalidade) -> dict:
    inscricoes = (
        await db_session.scalars(select(Inscricao).where(Inscricao.modalidade_id == modalidade.id))
    ).all()
    return {i.equipe_id: i.ordem_apresentacao for i in inscricoes}


async def test_sortear_ordem_numera_de_1_a_n_as_equipes_do_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    equipes = [await _inscrever(db_session, modalidade, f"Equipe {i}") for i in range(4)]

    await sortear_ordem(db_session, modalidade.id, nivel=1, usuario_id=coordenador.id)

    ordem = await _ordem_por_equipe(db_session, modalidade)
    assert sorted(ordem[e.id] for e in equipes) == [1, 2, 3, 4]


async def test_sortear_ordem_nao_mexe_em_outro_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    await _inscrever(db_session, modalidade, "Nivel 1")
    nivel_2 = await _inscrever(db_session, modalidade, "Nivel 2", nivel=2)

    await sortear_ordem(db_session, modalidade.id, nivel=1, usuario_id=coordenador.id)

    ordem = await _ordem_por_equipe(db_session, modalidade)
    assert ordem[nivel_2.id] is None


async def test_sortear_ordem_ignora_equipe_desativada(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    ativa = await _inscrever(db_session, modalidade, "Ativa")
    desativada = await _inscrever(db_session, modalidade, "Desativada", ativo=False)

    await sortear_ordem(db_session, modalidade.id, nivel=1, usuario_id=coordenador.id)

    ordem = await _ordem_por_equipe(db_session, modalidade)
    assert ordem[ativa.id] == 1
    assert ordem[desativada.id] is None


async def test_sortear_ordem_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    await _inscrever(db_session, modalidade, "Equipe A")

    await sortear_ordem(db_session, modalidade.id, nivel=1, usuario_id=coordenador.id)

    log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entidade_id == modalidade.id, AuditLog.acao == "SORTEAR_ORDEM"
        )
    )
    assert log is not None


async def test_sortear_ordem_recusa_modalidade_de_confronto(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, tipo=TipoDisputa.CONFRONTO)

    with pytest.raises(AppError) as erro:
        await sortear_ordem(db_session, modalidade.id, nivel=1, usuario_id=coordenador.id)
    assert erro.value.codigo == "ORDEM_SO_INDIVIDUAL"


async def test_definir_ordem_grava_a_sequencia_informada(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    a = await _inscrever(db_session, modalidade, "A")
    b = await _inscrever(db_session, modalidade, "B")
    c = await _inscrever(db_session, modalidade, "C")

    await definir_ordem(
        db_session, modalidade.id, nivel=1, equipe_ids=[c.id, a.id, b.id], usuario_id=coordenador.id
    )

    ordem = await _ordem_por_equipe(db_session, modalidade)
    assert (ordem[c.id], ordem[a.id], ordem[b.id]) == (1, 2, 3)


async def test_definir_ordem_recusa_lista_que_nao_bate_com_as_equipes_do_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    a = await _inscrever(db_session, modalidade, "A")
    await _inscrever(db_session, modalidade, "B")

    with pytest.raises(AppError) as erro:
        await definir_ordem(
            db_session, modalidade.id, nivel=1, equipe_ids=[a.id], usuario_id=coordenador.id
        )
    assert erro.value.codigo == "ORDEM_INCOMPLETA"


async def test_definir_ordem_recusa_equipe_repetida(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    a = await _inscrever(db_session, modalidade, "A")
    await _inscrever(db_session, modalidade, "B")

    with pytest.raises(AppError) as erro:
        await definir_ordem(
            db_session, modalidade.id, nivel=1, equipe_ids=[a.id, a.id], usuario_id=coordenador.id
        )
    assert erro.value.codigo == "ORDEM_INCOMPLETA"


# ---------- sequencia de competicao (lista + PDF pro telao) ----------


async def test_listar_sequencia_agrupa_por_nivel_na_ordem_definida(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    a = await _inscrever(db_session, modalidade, "Alfa")
    b = await _inscrever(db_session, modalidade, "Beta")
    await _inscrever(db_session, modalidade, "Delta", nivel=2)
    await definir_ordem(
        db_session, modalidade.id, nivel=1, equipe_ids=[b.id, a.id], usuario_id=coordenador.id
    )

    sequencia = await listar_sequencia(db_session, modalidade.id)

    assert [(s.nivel, [e.nome for e in s.equipes]) for s in sequencia] == [
        (1, ["Beta", "Alfa"]),
        (2, ["Delta"]),
    ]
    assert sequencia[0].sorteada is True
    assert sequencia[1].sorteada is False


async def test_listar_sequencia_sem_sorteio_usa_ordem_alfabetica(db_session):
    modalidade = await _criar_modalidade(db_session)
    await _inscrever(db_session, modalidade, "Zeta")
    await _inscrever(db_session, modalidade, "Alfa")

    sequencia = await listar_sequencia(db_session, modalidade.id)

    assert [e.nome for e in sequencia[0].equipes] == ["Alfa", "Zeta"]


async def test_listar_sequencia_marca_ausente_e_esconde_desativada(db_session):
    modalidade = await _criar_modalidade(db_session)
    await _inscrever(db_session, modalidade, "Presente")
    await _inscrever(db_session, modalidade, "Faltou", presente=False)
    await _inscrever(db_session, modalidade, "Desativada", ativo=False)

    sequencia = await listar_sequencia(db_session, modalidade.id)

    equipes = {e.nome: e.presente for e in sequencia[0].equipes}
    assert equipes == {"Presente": True, "Faltou": False}


async def test_gerar_sequencia_pdf_devolve_um_pdf(db_session):
    modalidade = await _criar_modalidade(db_session)
    await _inscrever(db_session, modalidade, "Alfa")
    await _inscrever(db_session, modalidade, "Delta", nivel=2)

    pdf = await gerar_sequencia_pdf(db_session, modalidade.id)

    assert pdf.startswith(b"%PDF")


async def test_gerar_sequencia_pdf_sem_equipe_ainda_gera_pdf(db_session):
    modalidade = await _criar_modalidade(db_session)

    pdf = await gerar_sequencia_pdf(db_session, modalidade.id)

    assert pdf.startswith(b"%PDF")
