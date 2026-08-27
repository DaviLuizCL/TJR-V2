import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_senha
from app.models.agendamento import Agendamento
from app.models.arena import Arena
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
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.consolidacao import calcular_classificacao
from app.services.ficha import depreciar_ficha, publicar_ficha
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento


async def _criar_arbitro(db_session, email="arbitro-consolidacao@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Arbitro", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_coordenador(db_session, email="coord-consolidacao@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(
    db_session,
    *,
    consolidacao=Consolidacao.SOMA_RODADAS,
    consolidacao_n=None,
    tentativas_por_rodada=1,
    desempates=None,
    qtd_rodadas=3,
) -> Modalidade:
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
        nome="Resgate no Plano",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=qtd_rodadas,
        tentativas_por_rodada=tentativas_por_rodada,
        consolidacao=consolidacao,
        consolidacao_n=consolidacao_n,
        desempates=desempates,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _criar_ficha(db_session, modalidade, criterios: dict[str, dict]) -> tuple[Ficha, dict]:
    ficha = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(ficha)
    await db_session.flush()
    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterios_por_chave = {}
    for chave, spec in criterios.items():
        criterio = Criterio(
            grupo_id=grupo.id,
            nome=spec.get("nome", chave),
            categoria=spec.get("categoria", CategoriaCriterio.PONTUACAO),
            tipo=spec.get("tipo", CriterioTipo.CONTADOR),
            pontos=spec.get("pontos", Decimal("1")),
            ordem=1,
            ativo=True,
        )
        db_session.add(criterio)
        await db_session.flush()
        criterios_por_chave[chave] = criterio

    return ficha, criterios_por_chave


async def _criar_rodada(db_session, modalidade, numero) -> Rodada:
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=numero,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    return rodada


async def _criar_equipe_inscrita(db_session, modalidade, nome, coordenador, nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )
    return equipe


async def _garantir_agendamento(db_session, ficha, rodada, equipe) -> None:
    existente = await db_session.scalar(
        select(Agendamento).where(
            Agendamento.rodada_id == rodada.id, Agendamento.equipe_id == equipe.id
        )
    )
    if existente is not None:
        return

    arena = Arena(
        modalidade_id=ficha.modalidade_id, nome="Arena 1", niveis_aplicaveis=None, ativo=True
    )
    db_session.add(arena)
    await db_session.flush()
    db_session.add(
        Agendamento(
            rodada_id=rodada.id,
            equipe_id=equipe.id,
            arena_id=arena.id,
            ordem_na_arena=0,
            horario_inicio=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        )
    )
    await db_session.flush()


async def _lancar(
    db_session,
    ficha,
    rodada,
    equipe,
    arbitro,
    itens_ocorrencias: dict,
    *,
    tentativa=1,
    confirmar=True,
    tempo_gasto_seg=None,
):
    await _garantir_agendamento(db_session, ficha, rodada, equipe)
    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=tentativa,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[
            ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)
            for criterio, ocorrencias in itens_ocorrencias.items()
        ],
        tempo_gasto_seg=tempo_gasto_seg,
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    if confirmar:
        lancamento = await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)
    return lancamento


def _nota(resultados, equipe_id) -> Decimal:
    return next(r for r in resultados if r["equipe_id"] == equipe_id)["nota_final"]


def _posicao(resultados, equipe_id) -> int:
    return next(r for r in resultados if r["equipe_id"] == equipe_id)["posicao"]


async def test_soma_rodadas_soma_a_melhor_tentativa_de_cada_rodada(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-1@tjr.app")
    modalidade = await _criar_modalidade(db_session, consolidacao=Consolidacao.SOMA_RODADAS)
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("5")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    r2 = await _criar_rodada(db_session, modalidade, 2)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 6})  # 30
    await _lancar(db_session, ficha, r2, equipe_a, arbitro, {criterios["c"]: 4})  # 20
    await _lancar(db_session, ficha, r1, equipe_b, arbitro, {criterios["c"]: 2})  # 10
    await _lancar(db_session, ficha, r2, equipe_b, arbitro, {criterios["c"]: 9})  # 45

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_b.id) == Decimal("55")
    assert _nota(resultados, equipe_a.id) == Decimal("50")
    assert _posicao(resultados, equipe_b.id) == 1
    assert _posicao(resultados, equipe_a.id) == 2


async def test_melhor_rodada_usa_apenas_a_maior_nota_de_rodada(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-2@tjr.app")
    modalidade = await _criar_modalidade(db_session, consolidacao=Consolidacao.MELHOR_RODADA)
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("5")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    r2 = await _criar_rodada(db_session, modalidade, 2)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 6})  # 30
    await _lancar(db_session, ficha, r2, equipe_a, arbitro, {criterios["c"]: 4})  # 20
    await _lancar(db_session, ficha, r1, equipe_b, arbitro, {criterios["c"]: 2})  # 10
    await _lancar(db_session, ficha, r2, equipe_b, arbitro, {criterios["c"]: 9})  # 45

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_b.id) == Decimal("45")
    assert _nota(resultados, equipe_a.id) == Decimal("30")


async def test_melhor_n_rodadas_soma_apenas_as_melhores_n(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-3@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        consolidacao=Consolidacao.MELHOR_N_RODADAS,
        consolidacao_n=2,
        qtd_rodadas=3,
    )
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    r2 = await _criar_rodada(db_session, modalidade, 2)
    r3 = await _criar_rodada(db_session, modalidade, 3)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 1})  # 10
    await _lancar(db_session, ficha, r2, equipe_a, arbitro, {criterios["c"]: 2})  # 20
    await _lancar(db_session, ficha, r3, equipe_a, arbitro, {criterios["c"]: 3})  # 30

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == Decimal("50")


async def test_ignora_menor_nota_soma_todas_as_rodadas_menos_a_pior(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-ignora-1@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        qtd_rodadas=3,
    )
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    r2 = await _criar_rodada(db_session, modalidade, 2)
    r3 = await _criar_rodada(db_session, modalidade, 3)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 1})  # 10 (pior)
    await _lancar(db_session, ficha, r2, equipe_a, arbitro, {criterios["c"]: 2})  # 20
    await _lancar(db_session, ficha, r3, equipe_a, arbitro, {criterios["c"]: 3})  # 30

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == Decimal("50")


async def test_ignora_menor_nota_com_apenas_uma_rodada_lancada_conta_ela_mesma(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-ignora-2@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        qtd_rodadas=3,
    )
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 2})  # 20

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == Decimal("20")


async def test_ignora_lancamento_pendente_e_conta_so_confirmado(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-4@tjr.app")
    modalidade = await _criar_modalidade(db_session)
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    await _lancar(
        db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 1}, tentativa=1, confirmar=False
    )
    await _lancar(
        db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 5}, tentativa=2, confirmar=True
    )

    resultados = await calcular_classificacao(db_session, modalidade.id)
    assert _nota(resultados, equipe_a.id) == Decimal("50")


async def test_melhor_tentativa_dentro_da_rodada_e_a_que_conta(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-5@tjr.app")
    modalidade = await _criar_modalidade(db_session, tentativas_por_rodada=2)
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("5")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 2}, tentativa=1)  # 10
    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 5}, tentativa=2)  # 25

    resultados = await calcular_classificacao(db_session, modalidade.id)
    assert _nota(resultados, equipe_a.id) == Decimal("25")


async def test_lancamento_de_ficha_depreciada_nao_conta_no_ranking(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-6@tjr.app")
    modalidade = await _criar_modalidade(db_session)
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 100})  # 1000
    await depreciar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    resultados = await calcular_classificacao(db_session, modalidade.id)
    assert _nota(resultados, equipe_a.id) == Decimal("0")


async def test_equipe_inscrita_sem_lancamento_aparece_com_nota_zero(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-7@tjr.app")
    modalidade = await _criar_modalidade(db_session)
    ficha, _criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == Decimal("0")


async def test_desempate_por_maior_total_em_uma_rodada(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-8@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        desempates=[{"tipo": "MAIOR_TOTAL_EM_UMA_RODADA", "direcao": "MAIOR"}],
    )
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("5")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    r2 = await _criar_rodada(db_session, modalidade, 2)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 5})  # 25
    await _lancar(db_session, ficha, r2, equipe_a, arbitro, {criterios["c"]: 5})  # 25 -> soma 50
    await _lancar(db_session, ficha, r1, equipe_b, arbitro, {criterios["c"]: 8})  # 40
    await _lancar(db_session, ficha, r2, equipe_b, arbitro, {criterios["c"]: 2})  # 10 -> soma 50

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == _nota(resultados, equipe_b.id) == Decimal("50")
    assert _posicao(resultados, equipe_b.id) == 1
    assert _posicao(resultados, equipe_a.id) == 2


async def test_desempate_por_menor_total_penalidades(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-9@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        desempates=[{"tipo": "MENOR_TOTAL_PENALIDADES", "direcao": "MENOR"}],
    )
    ficha, criterios = await _criar_ficha(
        db_session,
        modalidade,
        {
            "pontuacao": {"pontos": Decimal("10")},
            "penalidade": {"categoria": CategoriaCriterio.PENALIDADE, "pontos": Decimal("10")},
        },
    )
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    # A: 60 de pontuacao - 10 de penalidade = 50
    await _lancar(
        db_session,
        ficha,
        r1,
        equipe_a,
        arbitro,
        {criterios["pontuacao"]: 6, criterios["penalidade"]: 1},
    )
    # B: 70 de pontuacao - 20 de penalidade = 50
    await _lancar(
        db_session,
        ficha,
        r1,
        equipe_b,
        arbitro,
        {criterios["pontuacao"]: 7, criterios["penalidade"]: 2},
    )

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == _nota(resultados, equipe_b.id) == Decimal("50")
    assert _posicao(resultados, equipe_a.id) == 1
    assert _posicao(resultados, equipe_b.id) == 2


async def test_desempate_por_maior_pontuacao_no_criterio(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-10@tjr.app")
    modalidade = await _criar_modalidade(db_session)
    ficha, criterios = await _criar_ficha(
        db_session,
        modalidade,
        {"x": {"pontos": Decimal("10")}, "y": {"pontos": Decimal("10")}},
    )
    modalidade.desempates = [
        {
            "tipo": "MAIOR_PONTUACAO_NO_CRITERIO",
            "direcao": "MAIOR",
            "criterio_id": str(criterios["x"].id),
        }
    ]
    await db_session.flush()
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    # A: x=3 (30) + y=2 (20) = 50
    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["x"]: 3, criterios["y"]: 2})
    # B: x=1 (10) + y=4 (40) = 50
    await _lancar(db_session, ficha, r1, equipe_b, arbitro, {criterios["x"]: 1, criterios["y"]: 4})

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == _nota(resultados, equipe_b.id) == Decimal("50")
    assert _posicao(resultados, equipe_a.id) == 1
    assert _posicao(resultados, equipe_b.id) == 2


async def test_desempate_pula_menor_tempo_por_falta_de_dado_e_usa_proxima_regra(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-11@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        desempates=[
            {"tipo": "MENOR_TEMPO", "direcao": "MENOR"},
            {"tipo": "MAIOR_TOTAL_EM_UMA_RODADA", "direcao": "MAIOR"},
        ],
    )
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("5")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 10})  # 50
    await _lancar(db_session, ficha, r1, equipe_b, arbitro, {criterios["c"]: 10})  # 50

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert len(resultados) == 2
    assert {_posicao(resultados, equipe_a.id), _posicao(resultados, equipe_b.id)} == {1, 2}


async def test_desempate_por_menor_tempo_decide_quando_tempo_esta_registrado(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-tempo@tjr.app")
    modalidade = await _criar_modalidade(
        db_session,
        desempates=[{"tipo": "MENOR_TEMPO", "direcao": "MENOR"}],
    )
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("5")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "Equipe B", coordenador)

    # Empate em nota (50 pra cada), mas B foi mais rapida (90s < 120s) -- A
    # foi criada primeiro (ordem de insercao), entao se a regra nao fizer
    # nada de verdade a ordenacao estavel deixaria A na frente por acidente.
    await _lancar(
        db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 10}, tempo_gasto_seg=120
    )
    await _lancar(
        db_session, ficha, r1, equipe_b, arbitro, {criterios["c"]: 10}, tempo_gasto_seg=90
    )

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == _nota(resultados, equipe_b.id) == Decimal("50")
    assert _posicao(resultados, equipe_b.id) == 1
    assert _posicao(resultados, equipe_a.id) == 2


# ---------- ranking de confronto (todos-contra-todos e mata-mata) ----------


async def _criar_modalidade_confronto(
    db_session, *, formato, pontos_vitoria=3, pontos_empate=1
) -> Modalidade:
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
        formato_chaveamento=formato,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=5,
        consolidacao=Consolidacao.SOMA_RODADAS,
        pontos_vitoria=pontos_vitoria,
        pontos_empate=pontos_empate,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever_equipe_generica(db_session, modalidade, nome, coordenador, nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )
    return equipe


async def _criar_rodada_confronto(db_session, modalidade, numero=1) -> Rodada:
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=numero,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    return rodada


def _vitorias(resultados, equipe_id) -> int:
    return next(r for r in resultados if r["equipe_id"] == equipe_id)["vitorias"]


def _derrotas(resultados, equipe_id) -> int:
    return next(r for r in resultados if r["equipe_id"] == equipe_id)["derrotas"]


def _empates(resultados, equipe_id) -> int:
    return next(r for r in resultados if r["equipe_id"] == equipe_id)["empates"]


def _eliminado_por(resultados, equipe_id):
    return next(r for r in resultados if r["equipe_id"] == equipe_id)["eliminado_por_equipe_id"]


async def test_todos_contra_todos_calcula_pontos_de_liga(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-tct@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipe_a = await _inscrever_equipe_generica(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _inscrever_equipe_generica(db_session, modalidade, "Equipe B", coordenador)
    equipe_c = await _inscrever_equipe_generica(db_session, modalidade, "Equipe C", coordenador)
    rodada = await _criar_rodada_confronto(db_session, modalidade)

    # A bate B, A empata com C, B bate C
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_c.id,
            vencedor_id=None,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.EMPATADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_b.id,
            equipe_b_id=equipe_c.id,
            vencedor_id=equipe_b.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.ENCERRADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _vitorias(resultados, equipe_a.id) == 1
    assert _empates(resultados, equipe_a.id) == 1
    assert _nota(resultados, equipe_a.id) == Decimal("4")  # 3 + 1

    assert _vitorias(resultados, equipe_b.id) == 1
    assert _derrotas(resultados, equipe_b.id) == 1
    assert _nota(resultados, equipe_b.id) == Decimal("3")

    assert _empates(resultados, equipe_c.id) == 1
    assert _derrotas(resultados, equipe_c.id) == 1
    assert _nota(resultados, equipe_c.id) == Decimal("1")

    assert _posicao(resultados, equipe_a.id) == 1
    assert _posicao(resultados, equipe_b.id) == 2
    assert _posicao(resultados, equipe_c.id) == 3


async def test_mata_mata_ranking_mostra_vitorias_derrotas_e_eliminado_por(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-mm@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=FormatoChaveamento.MATA_MATA)
    equipe_a = await _inscrever_equipe_generica(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _inscrever_equipe_generica(db_session, modalidade, "Equipe B", coordenador)
    equipe_c = await _inscrever_equipe_generica(db_session, modalidade, "Equipe C", coordenador)
    equipe_d = await _inscrever_equipe_generica(db_session, modalidade, "Equipe D", coordenador)
    rodada1 = await _criar_rodada_confronto(db_session, modalidade, numero=1)
    rodada2 = await _criar_rodada_confronto(db_session, modalidade, numero=2)

    # Rodada 1: A bate B, C bate D. Rodada 2 (final): A bate C.
    db_session.add(
        Partida(
            rodada_id=rodada1.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada1.id,
            equipe_a_id=equipe_c.id,
            equipe_b_id=equipe_d.id,
            vencedor_id=equipe_c.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada2.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_c.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            status=PartidaStatus.ENCERRADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _vitorias(resultados, equipe_a.id) == 2
    assert _derrotas(resultados, equipe_a.id) == 0
    assert _eliminado_por(resultados, equipe_a.id) is None
    assert _posicao(resultados, equipe_a.id) == 1

    assert _vitorias(resultados, equipe_c.id) == 1
    assert _derrotas(resultados, equipe_c.id) == 1
    assert _eliminado_por(resultados, equipe_c.id) == equipe_a.id

    assert _derrotas(resultados, equipe_b.id) == 1
    assert _eliminado_por(resultados, equipe_b.id) == equipe_a.id

    assert _derrotas(resultados, equipe_d.id) == 1
    assert _eliminado_por(resultados, equipe_d.id) == equipe_c.id


# ---------- classificacao nao pode misturar niveis diferentes ----------


async def test_classificacao_individual_nao_mistura_niveis_diferentes(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-nivel-ind@tjr.app")
    modalidade = await _criar_modalidade(db_session)
    ficha, criterios = await _criar_ficha(db_session, modalidade, {"c": {"pontos": Decimal("10")}})
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    arbitro = await _criar_arbitro(db_session)
    r1 = await _criar_rodada(db_session, modalidade, 1)

    # Nivel 1: B tira nota maior que A. Nivel 2: C tira uma nota muito maior que ambos.
    equipe_a = await _criar_equipe_inscrita(db_session, modalidade, "N1 A", coordenador, nivel=1)
    equipe_b = await _criar_equipe_inscrita(db_session, modalidade, "N1 B", coordenador, nivel=1)
    equipe_c = await _criar_equipe_inscrita(db_session, modalidade, "N2 C", coordenador, nivel=2)

    await _lancar(db_session, ficha, r1, equipe_a, arbitro, {criterios["c"]: 3})  # 30
    await _lancar(db_session, ficha, r1, equipe_b, arbitro, {criterios["c"]: 5})  # 50
    await _lancar(db_session, ficha, r1, equipe_c, arbitro, {criterios["c"]: 100})  # 1000

    resultados = await calcular_classificacao(db_session, modalidade.id)

    # Cada nivel tem sua propria contagem de posicao 1..N — nao pode existir um
    # "1o lugar geral" que so ganhou por pertencer ao nivel de teto mais alto.
    assert _posicao(resultados, equipe_b.id) == 1
    assert _posicao(resultados, equipe_a.id) == 2
    assert _posicao(resultados, equipe_c.id) == 1


async def test_classificacao_bracket_nao_mistura_niveis_diferentes(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-nivel-mm@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=FormatoChaveamento.MATA_MATA)
    equipe_a = await _inscrever_equipe_generica(
        db_session, modalidade, "N1 A", coordenador, nivel=1
    )
    equipe_b = await _inscrever_equipe_generica(
        db_session, modalidade, "N1 B", coordenador, nivel=1
    )
    equipe_c = await _inscrever_equipe_generica(
        db_session, modalidade, "N2 C", coordenador, nivel=2
    )
    equipe_d = await _inscrever_equipe_generica(
        db_session, modalidade, "N2 D", coordenador, nivel=2
    )
    rodada1 = await _criar_rodada_confronto(db_session, modalidade, numero=1)

    # Nivel 1: A bate B (final do nivel 1, so 2 equipes). Nivel 2: C bate D (final do nivel 2).
    db_session.add(
        Partida(
            rodada_id=rodada1.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            nivel=1,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada1.id,
            equipe_a_id=equipe_c.id,
            equipe_b_id=equipe_d.id,
            vencedor_id=equipe_c.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            nivel=2,
            status=PartidaStatus.ENCERRADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    # Os campeoes dos dois niveis nao podem ficar em posicoes diferentes (1o e 2o
    # "geral") so por terem entrado no bracket em momentos diferentes — cada nivel
    # tem seu proprio campeao na posicao 1.
    assert _posicao(resultados, equipe_a.id) == 1
    assert _posicao(resultados, equipe_c.id) == 1
    assert _posicao(resultados, equipe_b.id) == 2
    assert _posicao(resultados, equipe_d.id) == 2


async def test_todos_contra_todos_desempate_por_confronto_direto(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-desempate-1@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipe_a = await _inscrever_equipe_generica(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _inscrever_equipe_generica(db_session, modalidade, "Equipe B", coordenador)
    equipe_c = await _inscrever_equipe_generica(db_session, modalidade, "Equipe C", coordenador)
    rodada = await _criar_rodada_confronto(db_session, modalidade)

    # A e C terminam empatados em pontos (1 vitoria, 1 derrota cada), mas
    # jogaram entre si e C venceu -- confronto direto deve colocar C na
    # frente de A, mesmo com a mesma pontuacao.
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_c.id,
            vencedor_id=equipe_c.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.ENCERRADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == _nota(resultados, equipe_c.id) == Decimal("3")
    assert _posicao(resultados, equipe_c.id) == 1
    assert _posicao(resultados, equipe_a.id) == 2
    assert _posicao(resultados, equipe_b.id) == 3


async def test_todos_contra_todos_desempate_cai_para_mais_vitorias_sem_confronto_direto(
    db_session,
):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-desempate-2@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session,
        formato=FormatoChaveamento.TODOS_CONTRA_TODOS,
        pontos_vitoria=1,
        pontos_empate=1,
    )
    equipe_a = await _inscrever_equipe_generica(db_session, modalidade, "Equipe A", coordenador)
    equipe_b = await _inscrever_equipe_generica(db_session, modalidade, "Equipe B", coordenador)
    equipe_c = await _inscrever_equipe_generica(db_session, modalidade, "Equipe C", coordenador)
    equipe_d = await _inscrever_equipe_generica(db_session, modalidade, "Equipe D", coordenador)
    rodada = await _criar_rodada_confronto(db_session, modalidade)

    # A vence C (1 ponto). B e D empatam entre si (1 ponto cada). A nunca
    # jogou contra B nem D -- sem confronto direto pra desempatar -- entao
    # cai pra "mais vitorias no total": A tem 1 vitoria, B e D tem 0.
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_c.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_b.id,
            equipe_b_id=equipe_d.id,
            vencedor_id=None,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            status=PartidaStatus.EMPATADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == Decimal("1")
    assert _nota(resultados, equipe_b.id) == Decimal("1")
    assert _nota(resultados, equipe_d.id) == Decimal("1")
    assert _posicao(resultados, equipe_a.id) == 1


async def test_classificacao_todos_contra_todos_nao_mistura_niveis_diferentes(db_session):
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-nivel-tct@tjr.app")
    modalidade = await _criar_modalidade_confronto(
        db_session, formato=FormatoChaveamento.TODOS_CONTRA_TODOS
    )
    equipe_a = await _inscrever_equipe_generica(
        db_session, modalidade, "N1 A", coordenador, nivel=1
    )
    equipe_b = await _inscrever_equipe_generica(
        db_session, modalidade, "N1 B", coordenador, nivel=1
    )
    equipe_c = await _inscrever_equipe_generica(
        db_session, modalidade, "N2 C", coordenador, nivel=2
    )
    equipe_d = await _inscrever_equipe_generica(
        db_session, modalidade, "N2 D", coordenador, nivel=2
    )
    rodada = await _criar_rodada_confronto(db_session, modalidade)

    # Nivel 1: A bate B. Nivel 2: C bate D.
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            nivel=1,
            status=PartidaStatus.ENCERRADA,
        )
    )
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_c.id,
            equipe_b_id=equipe_d.id,
            vencedor_id=equipe_c.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            nivel=2,
            status=PartidaStatus.ENCERRADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _posicao(resultados, equipe_a.id) == 1
    assert _posicao(resultados, equipe_c.id) == 1
    assert _posicao(resultados, equipe_b.id) == 2
    assert _posicao(resultados, equipe_d.id) == 2


async def test_classificacao_confronto_usa_formato_por_nivel_no_mesmo_calculo(db_session):
    # Cenario alvo do chaveamento por nivel: nivel 1 e todos-contra-todos
    # (nota de liga), nivel 2 e mata-mata (vitorias/derrotas/eliminado_por,
    # sem nota) - NA MESMA modalidade, modalidade.formato_chaveamento=None
    # (decisao automatica). calcular_classificacao precisa aplicar a formula
    # certa a cada equipe, olhando o formato da partida do nivel dela.
    coordenador = await _criar_coordenador(db_session, "coord-consolidacao-misto@tjr.app")
    modalidade = await _criar_modalidade_confronto(db_session, formato=None)
    equipe_a = await _inscrever_equipe_generica(
        db_session, modalidade, "N1 A", coordenador, nivel=1
    )
    equipe_b = await _inscrever_equipe_generica(
        db_session, modalidade, "N1 B", coordenador, nivel=1
    )
    equipe_c = await _inscrever_equipe_generica(
        db_session, modalidade, "N2 C", coordenador, nivel=2
    )
    equipe_d = await _inscrever_equipe_generica(
        db_session, modalidade, "N2 D", coordenador, nivel=2
    )
    rodada = await _criar_rodada_confronto(db_session, modalidade)

    # Nivel 1 (todos-contra-todos): A bate B -> A tem nota_final = pontos_vitoria.
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_a.id,
            equipe_b_id=equipe_b.id,
            vencedor_id=equipe_a.id,
            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
            nivel=1,
            status=PartidaStatus.ENCERRADA,
        )
    )
    # Nivel 2 (mata-mata): C bate D -> C tem 1 vitoria, sem nota.
    db_session.add(
        Partida(
            rodada_id=rodada.id,
            equipe_a_id=equipe_c.id,
            equipe_b_id=equipe_d.id,
            vencedor_id=equipe_c.id,
            formato_chaveamento=FormatoChaveamento.MATA_MATA,
            nivel=2,
            status=PartidaStatus.ENCERRADA,
        )
    )
    await db_session.flush()

    resultados = await calcular_classificacao(db_session, modalidade.id)

    assert _nota(resultados, equipe_a.id) == Decimal("3")
    assert _nota(resultados, equipe_b.id) == Decimal("0")
    assert _posicao(resultados, equipe_a.id) == 1
    assert _posicao(resultados, equipe_b.id) == 2

    assert _vitorias(resultados, equipe_c.id) == 1
    assert _derrotas(resultados, equipe_d.id) == 1
    assert _eliminado_por(resultados, equipe_d.id) == equipe_c.id
    assert _posicao(resultados, equipe_c.id) == 1
    assert _posicao(resultados, equipe_d.id) == 2
