import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.core.security import hash_senha
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.inscricao import Inscricao
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
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.chaveamento import criar_partida_manual
from app.services.ficha import publicar_ficha
from app.services.inscricao import criar_inscricao
from app.services.lancamento import confirmar_lancamento, criar_lancamento
from app.services.relatorio import (
    _calcular_gerado_em,
    _montar_secao_modalidade,
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


def test_calcular_gerado_em_retorna_horario_atual_nao_data_fixa():
    # Achado em teste de usabilidade: o "Gerado em" do relatorio estava preso
    # em evento.criado_em (quando o evento foi cadastrado), nao no horario
    # real do download -- dois downloads em dias diferentes mostravam a
    # mesma data antiga, minando a credibilidade do documento pra
    # contestacao (secao 1 do CLAUDE.md).
    antes = datetime.now(UTC)

    resultado = _calcular_gerado_em()

    depois = datetime.now(UTC)
    assert antes <= resultado.astimezone(UTC) <= depois


async def _montar_rodada_1(db_session, modalidade_id, *, usuario_id) -> Rodada:
    """Pareia as inscritas em ordem de inscricao (eliminatoria, Rodada 1) - o
    sistema nao gera chaveamento sozinho, entao o setup monta na mao.
    """
    ids = list(
        (
            await db_session.scalars(
                select(Inscricao.equipe_id)
                .where(Inscricao.modalidade_id == modalidade_id)
                .order_by(Inscricao.criado_em)
            )
        ).all()
    )
    partida = None
    for i in range(0, len(ids) - 1, 2):
        partida = await criar_partida_manual(
            db_session,
            modalidade_id,
            ids[i],
            ids[i + 1],
            rodada_numero=1,
            formato=FormatoChaveamento.MATA_MATA,
            usuario_id=usuario_id,
        )
    return await db_session.get(Rodada, partida.rodada_id)


async def test_gerar_relatorio_auditoria_pdf_retorna_pdf_valido_com_lancamento(db_session):
    coordenador = await _criar_coordenador(db_session)
    arbitro = await _criar_arbitro(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    equipes = await _inscrever_equipes(db_session, modalidade, coordenador, 4)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade, coordenador)

    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
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

    rodada = await _montar_rodada_1(db_session, modalidade.id, usuario_id=coordenador.id)
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

    rodada_a = await _montar_rodada_1(db_session, modalidade_a.id, usuario_id=coordenador.id)
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


def test_montar_secao_modalidade_nao_inclui_secao_de_lancamentos():
    from reportlab.lib.styles import getSampleStyleSheet

    modalidade = SimpleNamespace(tipo_disputa=TipoDisputa.INDIVIDUAL, formato_chaveamento=None)
    equipe_id = uuid.uuid4()
    classificacao = [{"equipe_id": equipe_id, "nota_final": 10, "posicao": 1}]
    equipes_por_id = {equipe_id: SimpleNamespace(nome="Equipe A", nivel=1)}

    elementos = _montar_secao_modalidade(
        getSampleStyleSheet(), modalidade, classificacao, equipes_por_id
    )

    textos = [getattr(e, "text", "") for e in elementos]
    assert any("Classifica" in t for t in textos)
    assert not any("Lancamento" in t or "Lançamento" in t for t in textos)


def test_montar_secao_modalidade_separa_cada_nivel_em_secao_propria():
    from reportlab.lib.styles import getSampleStyleSheet

    modalidade = SimpleNamespace(tipo_disputa=TipoDisputa.INDIVIDUAL, formato_chaveamento=None)
    equipe_n1 = uuid.uuid4()
    equipe_n2 = uuid.uuid4()
    # calcular_classificacao ja devolve os resultados agrupados por nivel
    # (services/consolidacao.py::_atribuir_posicoes_por_nivel) -- aqui simula
    # exatamente esse formato de entrada.
    classificacao = [
        {"equipe_id": equipe_n1, "nota_final": 10, "posicao": 1},
        {"equipe_id": equipe_n2, "nota_final": 20, "posicao": 1},
    ]
    equipes_por_id = {
        equipe_n1: SimpleNamespace(nome="Equipe Nivel 1", nivel=1),
        equipe_n2: SimpleNamespace(nome="Equipe Nivel 2", nivel=2),
    }

    elementos = _montar_secao_modalidade(
        getSampleStyleSheet(), modalidade, classificacao, equipes_por_id
    )

    textos = [getattr(e, "text", None) for e in elementos]
    indice_nivel_1 = textos.index("Nivel 1")
    indice_nivel_2 = textos.index("Nivel 2")
    assert indice_nivel_1 < indice_nivel_2

    tabela_nivel_1 = elementos[indice_nivel_1 + 1]
    linhas_nivel_1 = tabela_nivel_1._cellvalues
    assert any("Equipe Nivel 1" in str(celula) for linha in linhas_nivel_1 for celula in linha)
    assert not any("Equipe Nivel 2" in str(celula) for linha in linhas_nivel_1 for celula in linha)

    tabela_nivel_2 = elementos[indice_nivel_2 + 1]
    linhas_nivel_2 = tabela_nivel_2._cellvalues
    assert any("Equipe Nivel 2" in str(celula) for linha in linhas_nivel_2 for celula in linha)
    assert not any("Equipe Nivel 1" in str(celula) for linha in linhas_nivel_2 for celula in linha)
