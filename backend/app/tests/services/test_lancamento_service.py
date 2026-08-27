import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.agendamento import Agendamento
from app.models.arena import Arena
from app.models.audit_log import AuditLog
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCorrigir, LancamentoCreate
from app.services.lancamento import (
    confirmar_lancamento,
    corrigir_lancamento,
    criar_lancamento,
    listar_lancamentos,
    obter_lancamento_completo,
)


async def _criar_arbitro(db_session, email="arbitro-lancamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Arbitro", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.ARBITRO
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_coordenador(db_session, email="coord-lancamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(db_session, *, permite_total_negativo=False) -> Modalidade:
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
        nome="Sumo",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        permite_total_negativo=permite_total_negativo,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _criar_ficha_com_criterio(
    db_session,
    modalidade,
    *,
    tipo=CriterioTipo.CONTADOR,
    categoria=CategoriaCriterio.PONTUACAO,
    pontos=Decimal("10"),
    max_ocorrencias=None,
    valores_permitidos=None,
    modificador_tipo=None,
    modificador_valor=None,
) -> tuple[Ficha, Criterio]:
    ficha = Ficha(modalidade_id=modalidade.id, nivel=None, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(ficha)
    await db_session.flush()

    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=categoria,
        tipo=tipo,
        pontos=pontos,
        max_ocorrencias=max_ocorrencias,
        valores_permitidos=valores_permitidos,
        modificador_tipo=modificador_tipo,
        modificador_valor=modificador_valor,
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    await db_session.flush()
    return ficha, criterio


async def _criar_rodada(db_session, modalidade) -> Rodada:
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    await db_session.flush()
    return rodada


async def _criar_equipe(db_session, nome="Equipe A", nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    return equipe


async def _criar_agendamento(db_session, modalidade, rodada, equipe) -> Agendamento:
    arena = Arena(modalidade_id=modalidade.id, nome="Arena 1", niveis_aplicaveis=None, ativo=True)
    db_session.add(arena)
    await db_session.flush()

    agendamento = Agendamento(
        rodada_id=rodada.id,
        equipe_id=equipe.id,
        arena_id=arena.id,
        ordem_na_arena=0,
        horario_inicio=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
    )
    db_session.add(agendamento)
    await db_session.flush()
    return agendamento


async def _cenario_basico(db_session, **kwargs_modalidade):
    modalidade = await _criar_modalidade(db_session, **kwargs_modalidade)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade)
    rodada = await _criar_rodada(db_session, modalidade)
    equipe = await _criar_equipe(db_session)
    arbitro = await _criar_arbitro(db_session)
    await _criar_agendamento(db_session, modalidade, rodada, equipe)
    return modalidade, ficha, criterio, rodada, equipe, arbitro


def _payload(
    ficha,
    rodada,
    equipe,
    criterio,
    *,
    ocorrencias=3,
    client_operation_id=None,
    tempo_gasto_seg=None,
):
    return LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        partida_id=None,
        client_operation_id=client_operation_id or uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=ocorrencias)],
        tempo_gasto_seg=tempo_gasto_seg,
    )


async def test_criar_lancamento_calcula_total_via_servico_de_calculo(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio, ocorrencias=3), arbitro_id=arbitro.id
    )

    assert lancamento.total == Decimal("30")
    assert lancamento.status == LancamentoStatus.PENDENTE


async def test_criar_lancamento_grava_tempo_gasto_seg_quando_informado(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    lancamento = await criar_lancamento(
        db_session,
        _payload(ficha, rodada, equipe, criterio, tempo_gasto_seg=87),
        arbitro_id=arbitro.id,
    )

    assert lancamento.tempo_gasto_seg == 87


async def test_criar_lancamento_tempo_gasto_seg_e_opcional(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    assert lancamento.tempo_gasto_seg is None


async def test_criar_lancamento_grava_item_com_criterio_snapshot(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio, ocorrencias=2), arbitro_id=arbitro.id
    )
    completo = await obter_lancamento_completo(db_session, lancamento.id)

    assert len(completo.itens) == 1
    item = completo.itens[0]
    assert item.criterio_snapshot["nome"] == "Lombada"
    assert item.pontos == Decimal("20")
    assert item.ocorrencias == 2


async def test_criar_lancamento_grava_audit_log(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == lancamento.id)
    )
    log = resultado.scalar_one()
    assert log.entidade == "lancamento"
    assert log.acao == "CRIAR"


async def test_criar_lancamento_e_idempotente_por_client_operation_id(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    operacao_id = uuid.uuid4()

    primeiro = await criar_lancamento(
        db_session,
        _payload(ficha, rodada, equipe, criterio, client_operation_id=operacao_id),
        arbitro_id=arbitro.id,
    )
    segundo = await criar_lancamento(
        db_session,
        _payload(ficha, rodada, equipe, criterio, client_operation_id=operacao_id),
        arbitro_id=arbitro.id,
    )

    assert primeiro.id == segundo.id
    resultado = await db_session.execute(
        select(Lancamento).where(Lancamento.client_operation_id == operacao_id)
    )
    assert len(resultado.scalars().all()) == 1


async def test_criar_lancamento_recusa_segunda_equipe_rodada_tentativa_pendente(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    with pytest.raises(AppError) as exc_info:
        await criar_lancamento(
            db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
        )

    assert exc_info.value.codigo == "LANCAMENTO_JA_EXISTE"
    assert exc_info.value.status_code == 409
    resultado = await db_session.execute(
        select(Lancamento).where(
            Lancamento.rodada_id == rodada.id,
            Lancamento.equipe_id == equipe.id,
            Lancamento.tentativa == 1,
        )
    )
    assert len(resultado.scalars().all()) == 1


async def test_criar_lancamento_recusa_segunda_equipe_rodada_tentativa_confirmada(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    primeiro = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, primeiro.id, usuario_id=arbitro.id)

    with pytest.raises(AppError) as exc_info:
        await criar_lancamento(
            db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
        )

    assert exc_info.value.codigo == "LANCAMENTO_JA_EXISTE"


async def test_criar_lancamento_permite_novo_apos_o_anterior_ser_anulado(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    anterior = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    anterior.status = LancamentoStatus.ANULADO
    await db_session.flush()

    novo = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    assert novo.id != anterior.id


async def test_criar_lancamento_mesma_equipe_tentativas_diferentes_e_permitido(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    payload_tentativa_2 = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=2,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=3)],
    )
    segundo = await criar_lancamento(db_session, payload_tentativa_2, arbitro_id=arbitro.id)

    assert segundo.tentativa == 2


async def test_criar_lancamento_com_aplicado_em_criterio_nao_modificador_lanca_erro(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, aplicado=True)],
    )

    with pytest.raises(AppError) as exc_info:
        await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)

    assert exc_info.value.codigo == "CAMPO_APLICADO_INVALIDO_PARA_CRITERIO"
    assert exc_info.value.status_code == 422
    resultado = await db_session.execute(select(Lancamento))
    assert resultado.scalars().all() == []


async def test_corrigir_lancamento_com_aplicado_em_criterio_nao_modificador_lanca_erro(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    with pytest.raises(AppError) as exc_info:
        await corrigir_lancamento(
            db_session,
            lancamento.id,
            LancamentoCorrigir(
                justificativa="Corrigindo com campo errado",
                revision=1,
                itens=[ItemLancamentoInput(criterio_id=criterio.id, aplicado=True)],
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CAMPO_APLICADO_INVALIDO_PARA_CRITERIO"


async def test_criar_lancamento_com_criterio_fora_da_ficha_lanca_erro(db_session):
    _, ficha, _criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=uuid.uuid4(), ocorrencias=1)],
    )

    with pytest.raises(AppError) as exc_info:
        await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)

    assert exc_info.value.codigo == "CRITERIO_NAO_PERTENCE_A_FICHA"


async def test_criar_lancamento_individual_sem_arena_atribuida_lanca_erro(db_session):
    modalidade = await _criar_modalidade(db_session)
    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade)
    rodada = await _criar_rodada(db_session, modalidade)
    equipe = await _criar_equipe(db_session)
    arbitro = await _criar_arbitro(db_session)
    # nenhum Agendamento criado -- equipe nao foi atribuida a nenhuma arena nessa rodada

    with pytest.raises(AppError) as exc_info:
        await criar_lancamento(
            db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
        )

    assert exc_info.value.codigo == "EQUIPE_SEM_ARENA_ATRIBUIDA"
    resultado = await db_session.execute(select(Lancamento))
    assert resultado.scalars().all() == []


async def test_criar_lancamento_individual_com_arena_atribuida_funciona(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)

    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    assert lancamento.id is not None


async def test_criar_lancamento_confronto_nao_exige_arena_atribuida(db_session):
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
        nome="Sumo",
        tipo_disputa=TipoDisputa.CONFRONTO,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()

    ficha, criterio = await _criar_ficha_com_criterio(db_session, modalidade)
    rodada = await _criar_rodada(db_session, modalidade)
    equipe = await _criar_equipe(db_session)
    arbitro = await _criar_arbitro(db_session)
    # nenhum Agendamento criado -- CONFRONTO nao usa arena/agendamento neste sistema

    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    assert lancamento.id is not None


async def test_criar_lancamento_aplica_piso_zero_quando_nao_permite_negativo(db_session):
    modalidade, ficha, _c, rodada, equipe, arbitro = await _cenario_basico(
        db_session, permite_total_negativo=False
    )
    grupo = Grupo(ficha_id=ficha.id, nome="Penalidades", ordem=2)
    db_session.add(grupo)
    await db_session.flush()
    penalidade = Criterio(
        grupo_id=grupo.id,
        nome="Saiu da area",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("100"),
        ordem=1,
        ativo=True,
    )
    db_session.add(penalidade)
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=penalidade.id, ocorrencias=1)],
    )

    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)

    assert lancamento.total == Decimal("0")


async def test_confirmar_lancamento_muda_status(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )

    confirmado = await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    assert confirmado.status == LancamentoStatus.CONFIRMADO


async def test_confirmar_lancamento_ja_confirmado_lanca_erro(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    with pytest.raises(AppError) as exc_info:
        await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    assert exc_info.value.codigo == "LANCAMENTO_NAO_PENDENTE"


async def test_corrigir_lancamento_aceita_justificativa_vazia(db_session):
    # Justificativa e opcional de proposito (pedido explicito do cliente,
    # 2026-08-25) -- continua existindo no audit_log pra quem quiser
    # preencher, mas nao bloqueia mais a correcao quando vem em branco.
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    corrigido = await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            justificativa="",
            revision=1,
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=5)],
        ),
        usuario_id=coordenador.id,
    )

    assert corrigido.revision == 2


async def test_corrigir_lancamento_incrementa_revision_e_recalcula_total(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio, ocorrencias=3), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    corrigido = await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            justificativa="Arbitro contou errado",
            revision=1,
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=5)],
        ),
        usuario_id=coordenador.id,
    )

    assert corrigido.revision == 2
    assert corrigido.total == Decimal("50")
    assert corrigido.status == LancamentoStatus.CONFIRMADO

    completo = await obter_lancamento_completo(db_session, lancamento.id)
    assert len(completo.itens) == 1
    assert completo.itens[0].ocorrencias == 5


async def test_corrigir_lancamento_grava_audit_log_com_justificativa(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            justificativa="Correcao de contagem",
            revision=1,
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=1)],
        ),
        usuario_id=coordenador.id,
    )

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == lancamento.id, AuditLog.acao == "CORRIGIR")
    )
    log = resultado.scalar_one()
    assert log.justificativa == "Correcao de contagem"


async def test_corrigir_lancamento_com_revision_desatualizada_lanca_conflito(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio, ocorrencias=3), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    # Coordenador A corrige primeiro, revision vai de 1 pra 2.
    await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            justificativa="Primeira correcao",
            revision=1,
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=4)],
        ),
        usuario_id=coordenador.id,
    )

    # Coordenador B, que ainda estava vendo a tela com revision=1, tenta corrigir
    # em cima da mesma base desatualizada.
    with pytest.raises(AppError) as exc_info:
        await corrigir_lancamento(
            db_session,
            lancamento.id,
            LancamentoCorrigir(
                justificativa="Segunda correcao, concorrente",
                revision=1,
                itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=9)],
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "LANCAMENTO_REVISION_DESATUALIZADA"
    assert exc_info.value.status_code == 409
    assert exc_info.value.detalhes["revision_atual"] == 2

    # O estado da primeira correcao nao pode ter sido sobrescrito silenciosamente.
    atual = await obter_lancamento_completo(db_session, lancamento.id)
    assert atual.revision == 2
    assert atual.total == Decimal("40")


async def test_corrigir_lancamento_com_revision_atual_funciona_normalmente(db_session):
    _, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    lancamento = await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio, ocorrencias=3), arbitro_id=arbitro.id
    )
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    corrigido = await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            justificativa="Correcao com revision certa",
            revision=1,
            itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=4)],
        ),
        usuario_id=coordenador.id,
    )

    assert corrigido.revision == 2
    assert corrigido.total == Decimal("40")


async def test_corrigir_lancamento_omitindo_criterio_existente_lanca_erro(db_session):
    _, ficha, criterio_pontuacao, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    grupo_penalidade = Grupo(ficha_id=ficha.id, nome="Penalidades", ordem=2)
    db_session.add(grupo_penalidade)
    await db_session.flush()
    criterio_penalidade = Criterio(
        grupo_id=grupo_penalidade.id,
        nome="Saiu da area",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("5"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio_penalidade)
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[
            ItemLancamentoInput(criterio_id=criterio_pontuacao.id, ocorrencias=3),
            ItemLancamentoInput(criterio_id=criterio_penalidade.id, ocorrencias=1),
        ],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    # Correcao manda so o criterio de pontuacao, "esquecendo" a penalidade que
    # o lancamento original tinha.
    with pytest.raises(AppError) as exc_info:
        await corrigir_lancamento(
            db_session,
            lancamento.id,
            LancamentoCorrigir(
                justificativa="Corrigindo so a pontuacao",
                revision=1,
                itens=[ItemLancamentoInput(criterio_id=criterio_pontuacao.id, ocorrencias=5)],
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CORRECAO_OMITE_CRITERIO"
    assert exc_info.value.status_code == 422
    assert str(criterio_penalidade.id) in exc_info.value.detalhes["criterios_faltando"]

    # Nada foi alterado: lancamento continua na revision 1, com os itens originais.
    atual = await obter_lancamento_completo(db_session, lancamento.id)
    assert atual.revision == 1
    assert atual.total == Decimal("25")  # 30 de pontuacao - 5 de penalidade


async def test_corrigir_lancamento_cobrindo_todos_os_criterios_originais_funciona(db_session):
    _, ficha, criterio_pontuacao, rodada, equipe, arbitro = await _cenario_basico(db_session)
    coordenador = await _criar_coordenador(db_session)
    grupo_penalidade = Grupo(ficha_id=ficha.id, nome="Penalidades", ordem=2)
    db_session.add(grupo_penalidade)
    await db_session.flush()
    criterio_penalidade = Criterio(
        grupo_id=grupo_penalidade.id,
        nome="Saiu da area",
        categoria=CategoriaCriterio.PENALIDADE,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("5"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio_penalidade)
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[
            ItemLancamentoInput(criterio_id=criterio_pontuacao.id, ocorrencias=3),
            ItemLancamentoInput(criterio_id=criterio_penalidade.id, ocorrencias=1),
        ],
    )
    lancamento = await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)
    await confirmar_lancamento(db_session, lancamento.id, usuario_id=arbitro.id)

    corrigido = await corrigir_lancamento(
        db_session,
        lancamento.id,
        LancamentoCorrigir(
            justificativa="Zerando a penalidade de proposito, de forma explicita",
            revision=1,
            itens=[
                ItemLancamentoInput(criterio_id=criterio_pontuacao.id, ocorrencias=5),
                ItemLancamentoInput(criterio_id=criterio_penalidade.id, ocorrencias=0),
            ],
        ),
        usuario_id=coordenador.id,
    )

    assert corrigido.revision == 2
    assert corrigido.total == Decimal("50")


async def test_listar_lancamentos_filtra_por_rodada_e_equipe(db_session):
    modalidade, ficha, criterio, rodada, equipe, arbitro = await _cenario_basico(db_session)
    outra_equipe = await _criar_equipe(db_session, nome="Equipe B")
    await _criar_agendamento(db_session, modalidade, rodada, outra_equipe)

    await criar_lancamento(
        db_session, _payload(ficha, rodada, equipe, criterio), arbitro_id=arbitro.id
    )
    await criar_lancamento(
        db_session, _payload(ficha, rodada, outra_equipe, criterio), arbitro_id=arbitro.id
    )

    itens, total = await listar_lancamentos(
        db_session, rodada_id=rodada.id, equipe_id=equipe.id, page=1, size=50
    )

    assert total == 1
    assert itens[0].equipe_id == equipe.id
