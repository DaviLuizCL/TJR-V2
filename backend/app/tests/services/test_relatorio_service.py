import uuid
from datetime import date
from decimal import Decimal

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
from app.services.relatorio import gerar_relatorio_auditoria_pdf


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


async def _criar_modalidade_confronto(db_session) -> Modalidade:
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
        nome="Sumo de Robos",
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
    assert len(pdf_bytes) > 500


async def test_gerar_relatorio_auditoria_pdf_sem_nenhum_lancamento_nao_quebra(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    await _inscrever_equipes(db_session, modalidade, coordenador, 2)

    pdf_bytes = await gerar_relatorio_auditoria_pdf(db_session, modalidade.id)

    assert pdf_bytes.startswith(b"%PDF")
