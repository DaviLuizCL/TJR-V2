import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import (
    Consolidacao,
    DecisaoPartida,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.chave import ChaveCreate
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCorrigir, LancamentoCreate
from app.services.chave import adicionar_equipe, criar_chave
from app.services.chaveamento import (
    criar_partida_manual,
    registrar_resultado_lancamento,
    resetar_chaveamento,
)
from app.services.inscricao import criar_inscricao
from app.services.lancamento import (
    confirmar_lancamento,
    corrigir_lancamento,
    criar_lancamento,
)


async def _criar_coordenador(db_session, email="coord-chaveamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_arbitro(db_session, email="arbitro-chaveamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Arbitro", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade_confronto(
    db_session,
    *,
    nome="Combate",
    evento_id=None,
    formato=FormatoChaveamento.MATA_MATA,
    niveis_aplicaveis=None,
    tentativas_por_rodada=1,
    decisao_partida=DecisaoPartida.COMBATES_VENCIDOS,
) -> Modalidade:
    if evento_id is None:
        evento = Evento(
            nome="TJR 2026",
            ano=2026,
            data_inicio=date(2026, 3, 10),
            data_fim=date(2026, 3, 12),
            status=EventoStatus.RASCUNHO,
        )
        db_session.add(evento)
        await db_session.flush()
        evento_id = evento.id

    modalidade = Modalidade(
        evento_id=evento_id,
        nome=nome,
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=formato,
        niveis_aplicaveis=niveis_aplicaveis or [1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=5,
        tentativas_por_rodada=tentativas_por_rodada,
        consolidacao=Consolidacao.SOMA_RODADAS,
        decisao_partida=decisao_partida,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever_equipes(db_session, modalidade, coordenador, qtd, nivel=1) -> list[Equipe]:
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


async def _inscrever_equipes_por_nivel(db_session, modalidade, coordenador, niveis) -> list[Equipe]:
    """Cria uma equipe pra cada nivel da lista informada (ex.: [1, 1, 2, 2] cria
    2 equipes de nivel 1 e 2 de nivel 2), todas inscritas na mesma modalidade.
    """
    equipes = []
    for i, nivel in enumerate(niveis):
        equipe = Equipe(nome=f"Equipe {i + 1} Nivel {nivel}", nivel=nivel)
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
    from app.services.ficha import publicar_ficha

    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    return ficha, criterio


ELIMINATORIA = FormatoChaveamento.MATA_MATA
FASE_DE_GRUPOS = FormatoChaveamento.TODOS_CONTRA_TODOS


async def _montar_rodada_1(db_session, modalidade_id, *, usuario_id) -> Rodada:
    """Monta a Rodada 1 na mao (eliminatoria), pareando as inscritas de cada
    nivel em ordem de inscricao - so setup de teste, o sistema nao gera
    chaveamento sozinho.
    """
    resultado = await db_session.execute(
        select(Inscricao.equipe_id, Equipe.nivel)
        .join(Equipe, Inscricao.equipe_id == Equipe.id)
        .where(Inscricao.modalidade_id == modalidade_id)
        .order_by(Inscricao.criado_em)
    )
    por_nivel: dict[int, list] = {}
    for equipe_id, nivel in resultado.all():
        por_nivel.setdefault(nivel, []).append(equipe_id)
    partida = None
    for ids in por_nivel.values():
        for i in range(0, len(ids) - 1, 2):
            partida = await criar_partida_manual(
                db_session,
                modalidade_id,
                ids[i],
                ids[i + 1],
                rodada_numero=1,
                formato=ELIMINATORIA,
                usuario_id=usuario_id,
            )
    return await db_session.get(Rodada, partida.rodada_id)


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


# ---------- criar_partida_manual ----------


async def test_criar_partida_manual_cria_partida_na_rodada_informada(db_session):
    coordenador = await _criar_coordenador(db_session, "cp1@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    a, b = await _inscrever_equipes(db_session, modalidade, coordenador, 2)

    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=3,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    assert partida.equipe_a_id == a.id
    assert partida.equipe_b_id == b.id
    assert partida.nivel == a.nivel
    assert partida.status == PartidaStatus.AGENDADA
    rodada = await db_session.get(Rodada, partida.rodada_id)
    assert rodada.numero == 3
    assert rodada.modalidade_id == modalidade.id


async def test_criar_partida_manual_reaproveita_rodada_de_mesmo_numero(db_session):
    coordenador = await _criar_coordenador(db_session, "cp3@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    a, b, c, d = await _inscrever_equipes(db_session, modalidade, coordenador, 4)

    p1 = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=2,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )
    p2 = await criar_partida_manual(
        db_session,
        modalidade.id,
        c.id,
        d.id,
        rodada_numero=2,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    assert p1.rodada_id == p2.rodada_id


async def test_criar_partida_manual_grava_o_tipo_escolhido_na_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "cp9@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    a, b, c, d = await _inscrever_equipes(db_session, modalidade, coordenador, 4)

    grupos = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=FASE_DE_GRUPOS,
        usuario_id=coordenador.id,
    )
    eliminatoria = await criar_partida_manual(
        db_session,
        modalidade.id,
        c.id,
        d.id,
        rodada_numero=1,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    assert grupos.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS
    assert eliminatoria.formato_chaveamento == FormatoChaveamento.MATA_MATA


async def test_criar_partida_manual_permite_mesma_equipe_em_rodadas_diferentes(db_session):
    # Semifinal/final montadas na mao: a equipe ja jogou a rodada 1 (ate com
    # partida ainda aberta) e entra de novo na rodada 2.
    coordenador = await _criar_coordenador(db_session, "cp10@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    a, b, c = await _inscrever_equipes(db_session, modalidade, coordenador, 3)
    await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        c.id,
        rodada_numero=2,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    assert (await db_session.get(Rodada, partida.rodada_id)).numero == 2


async def test_criar_partida_manual_fase_de_grupos_recusa_bye(db_session):
    coordenador = await _criar_coordenador(db_session, "cp11@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    (a,) = await _inscrever_equipes(db_session, modalidade, coordenador, 1)

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            a.id,
            None,
            rodada_numero=1,
            formato=FASE_DE_GRUPOS,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "BYE_SO_EM_ELIMINATORIA"


async def test_criar_partida_manual_fase_de_grupos_preenche_chave_das_duas_equipes(db_session):
    coordenador = await _criar_coordenador(db_session, "cp12@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    a, b = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    await adicionar_equipe(db_session, chave.id, a.id, usuario_id=coordenador.id)
    await adicionar_equipe(db_session, chave.id, b.id, usuario_id=coordenador.id)

    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=FASE_DE_GRUPOS,
        usuario_id=coordenador.id,
    )

    assert partida.chave_id == chave.id


async def test_criar_partida_manual_sem_chave_em_comum_fica_sem_chave(db_session):
    coordenador = await _criar_coordenador(db_session, "cp13@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    a, b = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    await adicionar_equipe(db_session, chave.id, a.id, usuario_id=coordenador.id)

    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=FASE_DE_GRUPOS,
        usuario_id=coordenador.id,
    )

    assert partida.chave_id is None


async def test_criar_partida_manual_eliminatoria_nunca_carrega_chave(db_session):
    coordenador = await _criar_coordenador(db_session, "cp14@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    a, b = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    await adicionar_equipe(db_session, chave.id, a.id, usuario_id=coordenador.id)
    await adicionar_equipe(db_session, chave.id, b.id, usuario_id=coordenador.id)

    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    assert partida.chave_id is None


async def test_criar_partida_manual_com_uma_equipe_so_e_bye(db_session):
    coordenador = await _criar_coordenador(db_session, "cp2@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    (a,) = await _inscrever_equipes(db_session, modalidade, coordenador, 1)

    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        None,
        rodada_numero=1,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    assert partida.equipe_b_id is None
    assert partida.status == PartidaStatus.ENCERRADA
    assert partida.vencedor_id == a.id


async def test_criar_partida_manual_recusa_niveis_diferentes(db_session):
    coordenador = await _criar_coordenador(db_session, "cp4@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])
    equipes = await _inscrever_equipes_por_nivel(db_session, modalidade, coordenador, [1, 2])
    a, b = equipes

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            a.id,
            b.id,
            rodada_numero=1,
            formato=ELIMINATORIA,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "NIVEIS_INCOMPATIVEIS"


async def test_criar_partida_manual_recusa_equipe_nao_inscrita(db_session):
    coordenador = await _criar_coordenador(db_session, "cp5@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    (a,) = await _inscrever_equipes(db_session, modalidade, coordenador, 1)
    fora = Equipe(nome="Fora da modalidade", nivel=1)
    db_session.add(fora)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            a.id,
            fora.id,
            rodada_numero=1,
            formato=ELIMINATORIA,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "EQUIPE_NAO_INSCRITA"


async def test_criar_partida_manual_recusa_mesma_equipe_nos_dois_lados(db_session):
    coordenador = await _criar_coordenador(db_session, "cp6@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    (a,) = await _inscrever_equipes(db_session, modalidade, coordenador, 1)

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            a.id,
            a.id,
            rodada_numero=1,
            formato=ELIMINATORIA,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "EQUIPES_IGUAIS"


async def test_criar_partida_manual_recusa_equipe_que_ja_tem_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "cp7@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    a, b, c = await _inscrever_equipes(db_session, modalidade, coordenador, 3)
    await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=ELIMINATORIA,
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            a.id,
            c.id,
            rodada_numero=1,
            formato=ELIMINATORIA,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "EQUIPE_JA_TEM_PARTIDA"


async def test_criar_partida_manual_recusa_equipe_ausente(db_session):
    coordenador = await _criar_coordenador(db_session, "cp15@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    a, b = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    b.presente = False
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            a.id,
            b.id,
            rodada_numero=1,
            formato=ELIMINATORIA,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "EQUIPE_AUSENTE"


async def test_criar_partida_manual_recusa_modalidade_individual(db_session):
    coordenador = await _criar_coordenador(db_session, "cp8@tjr.app")
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
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    equipe = Equipe(nome="Equipe", nivel=1)
    db_session.add(equipe)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_partida_manual(
            db_session,
            modalidade.id,
            equipe.id,
            None,
            rodada_numero=1,
            formato=ELIMINATORIA,
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "MODALIDADE_NAO_E_CONFRONTO"


# ---------- registrar_resultado_lancamento + avancar_se_rodada_completa (integracao) ----------


async def test_confirmar_os_dois_lancamentos_fecha_a_partida_com_vencedor(db_session):
    coordenador = await _criar_coordenador(db_session, "c8@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a8@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 1)
    partida_meio = await db_session.get(Partida, partida.id)
    assert partida_meio.status == PartidaStatus.AGENDADA  # so uma equipe lancou ainda

    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 3)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_b.id


async def test_empate_nao_fecha_a_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "c9@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a9@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 2)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 2)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.AGENDADA
    assert partida_final.vencedor_id is None


async def test_fechar_todas_as_partidas_da_eliminatoria_nao_gera_proxima_rodada(db_session):
    # Chaveamento 100% manual: semifinal/final sao montadas pelo coordenador,
    # o sistema nunca cria rodada/partida sozinho quando uma rodada fecha.
    coordenador = await _criar_coordenador(db_session, "c10@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a10@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada1 = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    for partida in await listar_partidas_por_rodada(db_session, rodada1.id):
        equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
        equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_a, criterio, partida, arbitro, 1
        )
        await _lancar_e_confirmar(
            db_session, ficha, rodada1, equipe_b, criterio, partida, arbitro, 5
        )

    partidas = await listar_partidas_por_rodada(db_session, rodada1.id)
    assert all(p.status == PartidaStatus.ENCERRADA for p in partidas)
    resultado = await db_session.execute(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id)
    )
    assert [r.numero for r in resultado.scalars().all()] == [1]


async def test_todos_contra_todos_com_vencedor_fecha_partida_sem_avancar_rodada(db_session):
    coordenador = await _criar_coordenador(db_session, "c16@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a16@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 1)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[1], criterio, partida, arbitro, 3)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipes[1].id

    resultado = await db_session.execute(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id)
    )
    assert len(resultado.scalars().all()) == 1


async def test_todos_contra_todos_com_empate_marca_partida_empatada(db_session):
    coordenador = await _criar_coordenador(db_session, "c17@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a17@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 2)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[1], criterio, partida, arbitro, 2)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.EMPATADA
    assert partida_final.vencedor_id is None


async def test_registrar_resultado_usa_formato_da_partida_nao_da_modalidade(db_session):
    # Cenario alvo do chaveamento por nivel: modalidade.formato_chaveamento
    # fica None (decisao automatica por nivel, ver gerar_chaveamento_confronto),
    # entao quem decide o comportamento de uma partida especifica e o
    # formato_chaveamento gravado nela mesma, nao mais o campo da modalidade.
    coordenador = await _criar_coordenador(db_session, "c17b@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a17b@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 2)
    await _lancar_e_confirmar(db_session, ficha, rodada, equipes[1], criterio, partida, arbitro, 2)

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.EMPATADA


async def test_registrar_resultado_ignora_lancamento_sem_partida(db_session):
    coordenador = await _criar_coordenador(db_session, "c14@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a14@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipes[0].id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=1)],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    confirmado = await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    # nao deve levantar erro nem tentar fechar partida nenhuma (lancamento.partida_id e None)
    await registrar_resultado_lancamento(db_session, confirmado, usuario_id=arbitro.id)


# ---------- separacao do chaveamento por nivel ----------


# ---------- partida em melhor-de-3 (3 tentativas por partida) ----------


async def test_partida_so_fecha_apos_3_tentativas_confirmadas_dos_dois_lados(db_session):
    coordenador = await _criar_coordenador(db_session, "c22@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a22@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # equipe_a lanca os 3 combates; equipe_b so lanca o combate 1 (que ela
    # vence). A partida nao pode fechar so com esse combate isolado - precisa
    # dos 3 combates confirmados dos DOIS lados antes de decidir.
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 5, tentativa=1
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 9, tentativa=1
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 5, tentativa=2
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 5, tentativa=3
    )

    partida_meio = await db_session.get(Partida, partida.id)
    assert partida_meio.status == PartidaStatus.AGENDADA


async def test_vencedor_da_partida_e_quem_ganha_2_dos_3_combates(db_session):
    coordenador = await _criar_coordenador(db_session, "c23@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a23@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # combate 1: equipe_b vence disparado (1x9); combate 2 e 3: equipe_a vence
    # por pouco (2x1) -> equipe_a fecha a partida 2x1 mesmo perdendo o combate
    # 1 de goleada (prova que e por NUMERO de combates vencidos, nao por soma
    # de pontos - uma comparacao ingenua so do primeiro combate confirmado
    # de cada lado apontaria equipe_b como vencedora, o que seria errado).
    for tentativa, (pontos_a, pontos_b) in enumerate([(1, 9), (2, 1), (2, 1)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_a.id


async def test_combate_empatado_nao_conta_vitoria_pra_ninguem(db_session):
    coordenador = await _criar_coordenador(db_session, "c24@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a24@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # combate 1: empate (nao conta pra ninguem); combate 2 e 3: equipe_b vence
    # -> 2x0 pra equipe_b. Os valores sao escolhidos pra que uma comparacao
    # ingenua (so o 1o par de lancamentos confirmados de cada lado, sem
    # respeitar a tentativa) apontasse equipe_a como vencedora - o que seria
    # errado, ja que equipe_b venceu 2 dos 3 combates de verdade.
    for tentativa, (pontos_a, pontos_b) in enumerate([(2, 2), (5, 9), (1, 9)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_b.id


async def test_partida_mata_mata_fica_aberta_se_combates_empatam_1_1(db_session):
    coordenador = await _criar_coordenador(db_session, "c25@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a25@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    # combate 1: equipe_a vence; combate 2: equipe_b vence; combate 3: empate -> 1x1, sem vencedor
    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.AGENDADA
    assert partida_final.vencedor_id is None


async def test_mata_mata_combate_extra_de_desempate_fecha_a_partida(db_session):
    """Quando os 3 combates empatam 1x1 (com 1 combate empatado no meio), um
    combate extra na tentativa seguinte (tentativas_por_rodada + 1) decide a
    partida sem reescrever o resultado dos 3 combates anteriores - e o
    'ponto de ouro' descrito no CLAUDE.md, nao uma correcao de lancamento.
    """
    coordenador = await _criar_coordenador(db_session, "c27@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a27@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_antes = await db_session.get(Partida, partida.id)
    assert partida_antes.status == PartidaStatus.AGENDADA  # ainda 1x1, precisa do desempate

    # combate extra (tentativa 4): equipe_b vence -> decide a partida 2x1
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 1, tentativa=4
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 8, tentativa=4
    )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipe_b.id


async def test_mata_mata_combate_extra_tambem_empatado_mantem_partida_aberta(db_session):
    coordenador = await _criar_coordenador(db_session, "c28@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a28@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, tentativas_por_rodada=3)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    from app.services.partida import listar_partidas_por_rodada

    partida = (await listar_partidas_por_rodada(db_session, rodada.id))[0]
    equipe_a = next(e for e in equipes if e.id == partida.equipe_a_id)
    equipe_b = next(e for e in equipes if e.id == partida.equipe_b_id)

    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_a,
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipe_b,
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    # combate extra tambem empata -> continua sem vencedor (fica pro coordenador resolver)
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_a, criterio, partida, arbitro, 4, tentativa=4
    )
    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipe_b, criterio, partida, arbitro, 4, tentativa=4
    )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.AGENDADA
    assert partida_final.vencedor_id is None


async def test_todos_contra_todos_marca_empatada_quando_combates_empatam(db_session):
    coordenador = await _criar_coordenador(db_session, "c26@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a26@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS, tentativas_por_rodada=3
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    # combate 1: equipe[0] vence; combate 2: equipe[1] vence; combate 3: empate -> 1x1, EMPATADA
    for tentativa, (pontos_a, pontos_b) in enumerate([(5, 1), (1, 5), (3, 3)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[0],
            criterio,
            partida,
            arbitro,
            pontos_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[1],
            criterio,
            partida,
            arbitro,
            pontos_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.EMPATADA
    assert partida_final.vencedor_id is None


async def test_soma_pontos_decide_vencedor_pelo_total_mesmo_com_1_combate_vencido_cada(db_session):
    """Reproduz o cenario relatado: cada equipe vence 1 combate (1 a 1 na
    contagem, que empataria em COMBATES_VENCIDOS), mas o total de pontos
    somado dos 2 combates e diferente - com decisao_partida=SOMA_PONTOS a
    equipe com mais pontos no total vence a partida, nao empata.
    """
    coordenador = await _criar_coordenador(db_session, "c27soma@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a27soma@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session,
        formato=FormatoChaveamento.TODOS_CONTRA_TODOS,
        tentativas_por_rodada=2,
        decisao_partida=DecisaoPartida.SOMA_PONTOS,
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    # combate 1: equipe[0] vence 20x0; combate 2: equipe[1] vence 0x10.
    # 1 combate vencido cada (empataria em COMBATES_VENCIDOS), mas a soma dos
    # totais (20+0=20 contra 0+10=10) da vitoria pra equipe[0].
    for tentativa, (ocorrencias_a, ocorrencias_b) in enumerate([(2, 0), (0, 1)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[0],
            criterio,
            partida,
            arbitro,
            ocorrencias_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[1],
            criterio,
            partida,
            arbitro,
            ocorrencias_b,
            tentativa=tentativa,
        )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipes[0].id


async def test_soma_pontos_mata_mata_usa_ponto_de_ouro_quando_soma_tambem_empata(db_session):
    coordenador = await _criar_coordenador(db_session, "c28soma@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a28soma@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session,
        formato=FormatoChaveamento.MATA_MATA,
        tentativas_por_rodada=2,
        decisao_partida=DecisaoPartida.SOMA_PONTOS,
    )
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipes[0].id,
        equipe_b_id=equipes[1].id,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        status=PartidaStatus.AGENDADA,
    )
    db_session.add(partida)
    await db_session.flush()

    # combate 1: equipe[0] 20x0; combate 2: equipe[1] 0x20 -> soma 20x20, empata
    for tentativa, (ocorrencias_a, ocorrencias_b) in enumerate([(2, 0), (0, 2)], start=1):
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[0],
            criterio,
            partida,
            arbitro,
            ocorrencias_a,
            tentativa=tentativa,
        )
        await _lancar_e_confirmar(
            db_session,
            ficha,
            rodada,
            equipes[1],
            criterio,
            partida,
            arbitro,
            ocorrencias_b,
            tentativa=tentativa,
        )

    partida_apos_normais = await db_session.get(Partida, partida.id)
    assert partida_apos_normais.status == PartidaStatus.AGENDADA

    # ponto de ouro (tentativa 3): equipe[0] marca 10, equipe[1] marca 0 ->
    # soma vira 30x20, equipe[0] vence
    await _lancar_e_confirmar(
        db_session,
        ficha,
        rodada,
        equipes[0],
        criterio,
        partida,
        arbitro,
        1,
        tentativa=3,
    )
    await _lancar_e_confirmar(
        db_session,
        ficha,
        rodada,
        equipes[1],
        criterio,
        partida,
        arbitro,
        0,
        tentativa=3,
    )

    partida_final = await db_session.get(Partida, partida.id)
    assert partida_final.status == PartidaStatus.ENCERRADA
    assert partida_final.vencedor_id == equipes[0].id


# ---------- resetar_chaveamento ----------


async def test_resetar_chaveamento_recusa_modalidade_individual(db_session):
    coordenador = await _criar_coordenador(db_session, "c27@tjr.app")
    evento = Evento(
        nome="E",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    modalidade = Modalidade(
        evento_id=evento.id,
        nome="Individual",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await resetar_chaveamento(
            db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano"
        )

    assert exc_info.value.codigo == "RESET_APENAS_CONFRONTO"


async def test_resetar_chaveamento_sem_rodada_e_no_op(db_session):
    coordenador = await _criar_coordenador(db_session, "c28@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session)

    await resetar_chaveamento(
        db_session, modalidade.id, usuario_id=coordenador.id, justificativa="engano"
    )

    resultado = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entidade_id == modalidade.id, AuditLog.acao == "RESET_CHAVEAMENTO"
        )
    )
    assert resultado.scalar_one_or_none() is None


async def test_resetar_chaveamento_apaga_tudo_e_grava_snapshot_no_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session, "c29@tjr.app")
    arbitro = await _criar_arbitro(db_session, "a29@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=FormatoChaveamento.MATA_MATA)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)

    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
    resultado = await db_session.execute(select(Partida).where(Partida.rodada_id == rodada.id))
    partida = resultado.scalars().first()

    await _lancar_e_confirmar(
        db_session, ficha, rodada, equipes[0], criterio, partida, arbitro, 5, tentativa=1
    )

    await resetar_chaveamento(
        db_session,
        modalidade.id,
        usuario_id=coordenador.id,
        justificativa="Coordenacao pediu mata-mata, mas o formato certo era todos-contra-todos.",
    )

    assert (await db_session.get(Rodada, rodada.id)) is None
    assert (await db_session.get(Partida, partida.id)) is None
    resultado = await db_session.execute(
        select(Lancamento).where(Lancamento.rodada_id == rodada.id)
    )
    assert resultado.scalars().all() == []
    resultado = await db_session.execute(
        select(LancamentoItem).join(Lancamento).where(Lancamento.rodada_id == rodada.id)
    )
    assert resultado.scalars().all() == []

    resultado = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entidade_id == modalidade.id, AuditLog.acao == "RESET_CHAVEAMENTO"
        )
    )
    log = resultado.scalar_one()
    assert log.justificativa.startswith("Coordenacao pediu mata-mata")
    assert len(log.antes["rodadas"]) == 1
    assert len(log.antes["partidas"]) == 2
    assert len(log.antes["lancamentos"]) == 1
    assert len(log.antes["itens"]) == 1


# ---------- correcao de combate ja decidido ----------


async def _partida_com_um_combate(db_session, sufixo, formato):
    coordenador = await _criar_coordenador(db_session, f"corr-c{sufixo}@tjr.app")
    arbitro = await _criar_arbitro(db_session, f"corr-a{sufixo}@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    a, b = await _inscrever_equipes(db_session, modalidade, coordenador, 2)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)
    partida = await criar_partida_manual(
        db_session,
        modalidade.id,
        a.id,
        b.id,
        rodada_numero=1,
        formato=formato,
        usuario_id=coordenador.id,
    )
    rodada = await db_session.get(Rodada, partida.rodada_id)
    return coordenador, arbitro, ficha, criterio, rodada, partida, a, b


async def _corrigir(db_session, lancamento, criterio, ocorrencias, coordenador):
    return await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            revision=lancamento.revision,
            justificativa="juiz apertou errado",
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)],
        ),
        usuario_id=coordenador.id,
    )


async def test_corrigir_combate_inverte_o_vencedor_da_partida_ja_encerrada(db_session):
    coord, arbitro, ficha, criterio, rodada, partida, a, b = await _partida_com_um_combate(
        db_session, 1, ELIMINATORIA
    )
    lanc_a = await _lancar_e_confirmar(db_session, ficha, rodada, a, criterio, partida, arbitro, 1)
    await _lancar_e_confirmar(db_session, ficha, rodada, b, criterio, partida, arbitro, 5)
    assert (await db_session.get(Partida, partida.id)).vencedor_id == b.id

    await _corrigir(db_session, lanc_a, criterio, 9, coord)

    corrigida = await db_session.get(Partida, partida.id)
    assert corrigida.status == PartidaStatus.ENCERRADA
    assert corrigida.vencedor_id == a.id


async def test_corrigir_combate_eliminatorio_pra_empate_reabre_a_partida(db_session):
    # Eliminatoria nao aceita empate: volta a ficar aberta, esperando o
    # combate extra de desempate.
    coord, arbitro, ficha, criterio, rodada, partida, a, b = await _partida_com_um_combate(
        db_session, 2, ELIMINATORIA
    )
    await _lancar_e_confirmar(db_session, ficha, rodada, a, criterio, partida, arbitro, 1)
    lanc_b = await _lancar_e_confirmar(db_session, ficha, rodada, b, criterio, partida, arbitro, 5)

    await _corrigir(db_session, lanc_b, criterio, 1, coord)

    corrigida = await db_session.get(Partida, partida.id)
    assert corrigida.status == PartidaStatus.AGENDADA
    assert corrigida.vencedor_id is None


async def test_corrigir_combate_de_fase_de_grupos_pra_empate_marca_empatada(db_session):
    coord, arbitro, ficha, criterio, rodada, partida, a, b = await _partida_com_um_combate(
        db_session, 3, FASE_DE_GRUPOS
    )
    await _lancar_e_confirmar(db_session, ficha, rodada, a, criterio, partida, arbitro, 1)
    lanc_b = await _lancar_e_confirmar(db_session, ficha, rodada, b, criterio, partida, arbitro, 5)

    await _corrigir(db_session, lanc_b, criterio, 1, coord)

    corrigida = await db_session.get(Partida, partida.id)
    assert corrigida.status == PartidaStatus.EMPATADA
    assert corrigida.vencedor_id is None


async def test_corrigir_combate_de_partida_empatada_decide_o_vencedor(db_session):
    coord, arbitro, ficha, criterio, rodada, partida, a, b = await _partida_com_um_combate(
        db_session, 4, FASE_DE_GRUPOS
    )
    await _lancar_e_confirmar(db_session, ficha, rodada, a, criterio, partida, arbitro, 2)
    lanc_b = await _lancar_e_confirmar(db_session, ficha, rodada, b, criterio, partida, arbitro, 2)
    assert (await db_session.get(Partida, partida.id)).status == PartidaStatus.EMPATADA

    await _corrigir(db_session, lanc_b, criterio, 3, coord)

    corrigida = await db_session.get(Partida, partida.id)
    assert corrigida.status == PartidaStatus.ENCERRADA
    assert corrigida.vencedor_id == b.id
