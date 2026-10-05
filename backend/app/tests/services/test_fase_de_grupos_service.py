import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_senha
from app.models.chave import Chave, ChaveEquipe
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.usuario import Papel, Usuario
from app.schemas.chave import ChaveCreate
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.chave import adicionar_equipe, criar_chave
from app.services.chaveamento import criar_partida_manual
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento


async def _criar_coordenador(db_session, email="coord-fg@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_arbitro(db_session, email="arbitro-fg@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Arbitro", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade_confronto(db_session, *, tentativas_por_rodada=1) -> Modalidade:
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
        nome="Combate",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=None,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=5,
        tentativas_por_rodada=tentativas_por_rodada,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever(db_session, modalidade, coordenador, qtd, nivel=1) -> list[Equipe]:
    equipes = []
    for i in range(qtd):
        equipe = Equipe(nome=f"Equipe {i + 1}", nivel=nivel)
        db_session.add(equipe)
        await db_session.flush()
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )
        equipes.append(equipe)
    return equipes


async def _criar_chave_com_equipes(db_session, modalidade, coordenador, nome, equipes):
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome=nome),
        usuario_id=coordenador.id,
    )
    for equipe in equipes:
        await adicionar_equipe(db_session, chave.id, equipe.id, usuario_id=coordenador.id)
    return chave


async def _criar_ficha_com_criterio(db_session, modalidade, coordenador):
    from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
    from app.models.ficha import Ficha, FichaStatus
    from app.models.grupo import Grupo
    from app.services.ficha import publicar_ficha

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


async def _lancar_e_confirmar(
    db_session, ficha, rodada, equipe, criterio, partida, arbitro, ocorrencias, tentativa=1
):
    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=tentativa,
        equipe_id=equipe.id,
        partida_id=partida.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    return await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)


# ---------- resetar_chaveamento tambem limpa chave/chave_equipe ----------


async def test_resetar_chaveamento_tambem_apaga_chave_e_chave_equipe(db_session):
    from app.services.chaveamento import resetar_chaveamento

    coordenador = await _criar_coordenador(db_session, "fg11@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 2)
    chave = await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    await criar_partida_manual(
        db_session,
        modalidade.id,
        equipes[0].id,
        equipes[1].id,
        rodada_numero=1,
        formato=FormatoChaveamento.TODOS_CONTRA_TODOS,
        usuario_id=coordenador.id,
    )

    await resetar_chaveamento(
        db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano de chave"
    )

    assert (await db_session.get(Chave, chave.id)) is None
    resultado = await db_session.execute(
        select(ChaveEquipe).where(ChaveEquipe.chave_id == chave.id)
    )
    assert resultado.scalars().all() == []
