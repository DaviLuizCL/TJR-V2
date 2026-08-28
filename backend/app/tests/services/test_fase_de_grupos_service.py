import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
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
from app.models.partida import Partida
from app.models.rodada import Rodada
from app.models.usuario import Papel, Usuario
from app.schemas.chave import ChaveCreate
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.chave import adicionar_equipe, criar_chave
from app.services.chaveamento import criar_partida_manual, gerar_fase_de_grupos
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento
from app.services.partida import listar_partidas_por_rodada


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


# ---------- gerar_fase_de_grupos ----------


async def test_gerar_fase_de_grupos_recusa_sem_chave(db_session):
    coordenador = await _criar_coordenador(db_session, "fg1@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)

    with pytest.raises(AppError) as exc_info:
        await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "NENHUMA_CHAVE_PENDENTE"


async def test_gerar_fase_de_grupos_rejeita_chave_com_menos_de_duas_equipes(db_session):
    coordenador = await _criar_coordenador(db_session, "fg2@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 1)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)

    with pytest.raises(AppError) as exc_info:
        await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "CHAVE_SEM_EQUIPES_SUFICIENTES"


async def test_gerar_fase_de_grupos_cria_partidas_todos_contra_todos_por_chave(db_session):
    coordenador = await _criar_coordenador(db_session, "fg3@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 4)
    chave_a = await _criar_chave_com_equipes(
        db_session, modalidade, coordenador, "Chave A", equipes[:2]
    )
    chave_b = await _criar_chave_com_equipes(
        db_session, modalidade, coordenador, "Chave B", equipes[2:]
    )

    rodadas = await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    todas_partidas = []
    for rodada in rodadas:
        todas_partidas.extend(await listar_partidas_por_rodada(db_session, rodada.id))

    partidas_a = [p for p in todas_partidas if p.chave_id == chave_a.id]
    partidas_b = [p for p in todas_partidas if p.chave_id == chave_b.id]
    assert len(partidas_a) == 1
    assert len(partidas_b) == 1
    assert all(
        p.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS for p in todas_partidas
    )
    assert {partidas_a[0].equipe_a_id, partidas_a[0].equipe_b_id} == {e.id for e in equipes[:2]}
    assert {partidas_b[0].equipe_a_id, partidas_b[0].equipe_b_id} == {e.id for e in equipes[2:]}


async def test_gerar_fase_de_grupos_e_idempotente_pula_chave_que_ja_tem_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "fg4@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 4)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes[:2])
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    chave_b = await _criar_chave_com_equipes(
        db_session, modalidade, coordenador, "Chave B", equipes[2:]
    )
    rodadas = await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    todas_partidas = []
    for rodada in rodadas:
        todas_partidas.extend(await listar_partidas_por_rodada(db_session, rodada.id))
    # a rodada retornada e a rodada 1, reaproveitada entre as duas chamadas
    # (as duas chaves so precisam de 1 rodada) -- a chave B (nova) aparece
    # nela, sem duplicar a partida que a chave A ja tinha da 1a chamada.
    assert any(p.chave_id == chave_b.id for p in todas_partidas)

    resultado = await db_session.execute(select(Partida))
    assert len(resultado.scalars().all()) == 2  # 1 da chave A (1a chamada) + 1 da chave B


async def test_gerar_fase_de_grupos_recusa_quando_todas_as_chaves_ja_tem_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "fg5@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 2)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "NENHUMA_CHAVE_PENDENTE"


async def test_gerar_fase_de_grupos_intercala_rodadas_com_chaves_de_tamanhos_diferentes(db_session):
    coordenador = await _criar_coordenador(db_session, "fg6@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 7)
    # Chave A com 2 equipes (1 rodada necessaria), Chave B com 5 (5 rodadas necessarias - impar).
    chave_a = await _criar_chave_com_equipes(
        db_session, modalidade, coordenador, "Chave A", equipes[:2]
    )
    chave_b = await _criar_chave_com_equipes(
        db_session, modalidade, coordenador, "Chave B", equipes[2:]
    )

    rodadas = await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    assert len(rodadas) == 5
    partidas_rodada1 = await listar_partidas_por_rodada(db_session, rodadas[0].id)
    assert {p.chave_id for p in partidas_rodada1} == {chave_a.id, chave_b.id}
    partidas_rodada5 = await listar_partidas_por_rodada(db_session, rodadas[-1].id)
    # chave A (2 equipes) ja esgotou seu unico confronto possivel na rodada 1
    assert {p.chave_id for p in partidas_rodada5} == {chave_b.id}


# ---------- criar_partida_manual apos fase de grupos ----------


async def test_criar_partida_manual_aceita_equipe_que_ja_jogou_fase_de_grupos(db_session):
    coordenador = await _criar_coordenador(db_session, "fg7@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 2)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    partida = await criar_partida_manual(
        db_session, modalidade.id, equipes[0].id, equipes[1].id, usuario_id=coordenador.id
    )

    assert partida.formato_chaveamento == FormatoChaveamento.MATA_MATA
    rodada = await db_session.get(Rodada, partida.rodada_id)
    assert rodada.numero == 2  # fase de grupos usou so a rodada 1 (2 equipes = 1 rodada)


async def test_criar_partida_manual_rejeita_equipe_que_ja_tem_partida_na_rodada_alvo(db_session):
    coordenador = await _criar_coordenador(db_session, "fg8@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 4)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    await criar_partida_manual(
        db_session, modalidade.id, equipes[0].id, equipes[1].id, usuario_id=coordenador.id
    )

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session, modalidade.id, equipes[0].id, equipes[2].id, usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "EQUIPE_JA_TEM_PARTIDA"


async def test_criar_partida_manual_segunda_chamada_pos_grupos_reaproveita_a_mesma_rodada(
    db_session,
):
    coordenador = await _criar_coordenador(db_session, "fg9@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 4)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    p1 = await criar_partida_manual(
        db_session, modalidade.id, equipes[0].id, equipes[1].id, usuario_id=coordenador.id
    )
    p2 = await criar_partida_manual(
        db_session, modalidade.id, equipes[2].id, equipes[3].id, usuario_id=coordenador.id
    )

    assert p1.rodada_id == p2.rodada_id


async def test_avancar_se_rodada_completa_funciona_sozinho_a_partir_da_segunda_rodada_pos_grupos(
    db_session,
):
    coordenador = await _criar_coordenador(db_session, "fg10@tjr.app")
    arbitro = await _criar_arbitro(db_session, "afg10@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 4)
    await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    # coordenador monta a 1a rodada do mata-mata na mao com os "classificados"
    p1 = await criar_partida_manual(
        db_session, modalidade.id, equipes[0].id, equipes[1].id, usuario_id=coordenador.id
    )
    p2 = await criar_partida_manual(
        db_session, modalidade.id, equipes[2].id, equipes[3].id, usuario_id=coordenador.id
    )
    rodada_mata_mata = await db_session.get(Rodada, p1.rodada_id)

    for partida, (vencedor, perdedor) in (
        (p1, (equipes[1], equipes[0])),
        (p2, (equipes[3], equipes[2])),
    ):
        await _lancar_e_confirmar(
            db_session, ficha, rodada_mata_mata, perdedor, criterio, partida, arbitro, 1
        )
        await _lancar_e_confirmar(
            db_session, ficha, rodada_mata_mata, vencedor, criterio, partida, arbitro, 5
        )

    # sem nenhuma chamada manual: a final apareceu sozinha, gerada pelo
    # avanco automatico (registrar_resultado_lancamento -> avancar_se_rodada_completa).
    proxima = await db_session.scalar(
        select(Rodada).where(
            Rodada.modalidade_id == modalidade.id, Rodada.numero == rodada_mata_mata.numero + 1
        )
    )
    assert proxima is not None
    final = await listar_partidas_por_rodada(db_session, proxima.id)
    assert len(final) == 1
    assert {final[0].equipe_a_id, final[0].equipe_b_id} == {equipes[1].id, equipes[3].id}


# ---------- resetar_chaveamento tambem limpa chave/chave_equipe ----------


async def test_resetar_chaveamento_tambem_apaga_chave_e_chave_equipe(db_session):
    from app.services.chaveamento import resetar_chaveamento

    coordenador = await _criar_coordenador(db_session, "fg11@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever(db_session, modalidade, coordenador, 2)
    chave = await _criar_chave_com_equipes(db_session, modalidade, coordenador, "Chave A", equipes)
    await gerar_fase_de_grupos(db_session, modalidade.id, usuario_id=coordenador.id)

    await resetar_chaveamento(
        db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano de chave"
    )

    assert (await db_session.get(Chave, chave.id)) is None
    resultado = await db_session.execute(
        select(ChaveEquipe).where(ChaveEquipe.chave_id == chave.id)
    )
    assert resultado.scalars().all() == []
