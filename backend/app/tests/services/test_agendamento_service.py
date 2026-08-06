import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.agendamento import Agendamento
from app.models.arena import Arena
from app.models.audit_log import AuditLog
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.inscricao import InscricaoCreate
from app.services.agendamento import gerar_agendamentos
from app.services.inscricao import criar_inscricao


async def _criar_coordenador(db_session, email="coord-agendamento@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(
    db_session,
    *,
    tipo_disputa=TipoDisputa.INDIVIDUAL,
    niveis_aplicaveis=None,
    qtd_rodadas=3,
    duracao_maxima_rodada_seg=300,
    pausa_entre_rodadas_seg=None,
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
        tipo_disputa=tipo_disputa,
        niveis_aplicaveis=niveis_aplicaveis or [1, 2, 3, 4],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=qtd_rodadas,
        duracao_maxima_rodada_seg=duracao_maxima_rodada_seg,
        pausa_entre_rodadas_seg=pausa_entre_rodadas_seg,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


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


async def _criar_equipe_inscrita(
    db_session, modalidade, coordenador, *, nome, nivel, equipe_id=None
) -> Equipe:
    equipe = (
        Equipe(id=equipe_id, nome=nome, nivel=nivel)
        if equipe_id
        else Equipe(nome=nome, nivel=nivel)
    )
    db_session.add(equipe)
    await db_session.flush()
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )
    return equipe


async def _criar_arena(
    db_session, modalidade, *, nome, niveis_aplicaveis=None, ativo=True, arena_id=None
) -> Arena:
    kwargs = dict(
        modalidade_id=modalidade.id,
        nome=nome,
        niveis_aplicaveis=niveis_aplicaveis,
        ativo=ativo,
    )
    if arena_id is not None:
        kwargs["id"] = arena_id
    arena = Arena(**kwargs)
    db_session.add(arena)
    await db_session.flush()
    return arena


async def _agendamentos_da_rodada(db_session, rodada_id):
    resultado = await db_session.execute(
        select(Agendamento)
        .where(Agendamento.rodada_id == rodada_id)
        .order_by(Agendamento.ordem_na_arena)
    )
    return list(resultado.scalars().all())


async def test_gerar_agendamentos_calcula_ordem_e_horario_corretamente(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, niveis_aplicaveis=[1], duracao_maxima_rodada_seg=300
    )
    rodada = await _criar_rodada(db_session, modalidade, 1)

    arena_a = await _criar_arena(
        db_session, modalidade, nome="Arena A", arena_id=uuid.UUID(int=100)
    )
    arena_b = await _criar_arena(
        db_session, modalidade, nome="Arena B", arena_id=uuid.UUID(int=101)
    )

    equipes = [
        await _criar_equipe_inscrita(
            db_session,
            modalidade,
            coordenador,
            nome=f"Equipe {i}",
            nivel=1,
            equipe_id=uuid.UUID(int=i),
        )
        for i in range(1, 5)
    ]

    inicio = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    resultado = await gerar_agendamentos(
        db_session, modalidade.id, [rodada.id], inicio, usuario_id=coordenador.id
    )

    assert len(resultado) == 4

    por_equipe = {a.equipe_id: a for a in resultado}
    # Equipe 1 e 3 (indices pares na ordem de sorteio por id) caem na Arena A;
    # Equipe 2 e 4 na Arena B -- balanceamento de fila com desempate por
    # menor arena_id em cada empate.
    assert por_equipe[equipes[0].id].arena_id == arena_a.id
    assert por_equipe[equipes[0].id].ordem_na_arena == 0
    assert por_equipe[equipes[0].id].horario_inicio == inicio

    assert por_equipe[equipes[1].id].arena_id == arena_b.id
    assert por_equipe[equipes[1].id].ordem_na_arena == 0
    assert por_equipe[equipes[1].id].horario_inicio == inicio

    assert por_equipe[equipes[2].id].arena_id == arena_a.id
    assert por_equipe[equipes[2].id].ordem_na_arena == 1
    assert por_equipe[equipes[2].id].horario_inicio == inicio + timedelta(seconds=300)

    assert por_equipe[equipes[3].id].arena_id == arena_b.id
    assert por_equipe[equipes[3].id].ordem_na_arena == 1
    assert por_equipe[equipes[3].id].horario_inicio == inicio + timedelta(seconds=300)

    rodada_atualizada = await db_session.get(Rodada, rodada.id)
    assert rodada_atualizada.horario_inicio == inicio
    assert rodada_atualizada.modo_horario == ModoHorario.AUTOMATICO


async def test_gerar_agendamentos_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1])
    rodada = await _criar_rodada(db_session, modalidade, 1)
    await _criar_arena(db_session, modalidade, nome="Arena A")
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe 1", nivel=1)

    await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade == "rodada", AuditLog.acao == "GERAR_AGENDAMENTO")
    )
    assert resultado.scalar_one() is not None


async def test_gerar_agendamentos_respeita_niveis_aplicaveis_da_arena(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])
    rodada = await _criar_rodada(db_session, modalidade, 1)

    arena_nivel1 = await _criar_arena(
        db_session, modalidade, nome="So Nivel 1", niveis_aplicaveis=[1]
    )
    arena_aberta = await _criar_arena(db_session, modalidade, nome="Aberta", niveis_aplicaveis=None)

    equipe_n2 = await _criar_equipe_inscrita(
        db_session, modalidade, coordenador, nome="Equipe N2", nivel=2
    )
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe N1", nivel=1)

    resultado = await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )

    agendamento_n2 = next(a for a in resultado if a.equipe_id == equipe_n2.id)
    assert agendamento_n2.arena_id == arena_aberta.id
    assert agendamento_n2.arena_id != arena_nivel1.id


async def test_gerar_agendamentos_erro_quando_equipe_sem_arena_elegivel_nao_grava_nada(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])
    rodada = await _criar_rodada(db_session, modalidade, 1)
    await _criar_arena(db_session, modalidade, nome="So Nivel 1", niveis_aplicaveis=[1])
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe N2", nivel=2)

    with pytest.raises(AppError) as exc_info:
        await gerar_agendamentos(
            db_session,
            modalidade.id,
            [rodada.id],
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "ARENA_ELEGIVEL_INEXISTENTE"
    assert await _agendamentos_da_rodada(db_session, rodada.id) == []


async def test_gerar_agendamentos_rotaciona_arena_entre_lotes_separados(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1], qtd_rodadas=3)
    rodada1 = await _criar_rodada(db_session, modalidade, 1)
    rodada2 = await _criar_rodada(db_session, modalidade, 2)
    rodada3 = await _criar_rodada(db_session, modalidade, 3)

    arena_a = await _criar_arena(db_session, modalidade, nome="Arena A")
    arena_b = await _criar_arena(db_session, modalidade, nome="Arena B")
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe Solo", nivel=1)

    await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada1.id, rodada2.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )
    agendamentos_1_2 = await _agendamentos_da_rodada(
        db_session, rodada1.id
    ) + await _agendamentos_da_rodada(db_session, rodada2.id)
    arenas_usadas = {a.arena_id for a in agendamentos_1_2}
    assert arenas_usadas == {arena_a.id, arena_b.id}  # ciclo completo nas duas rodadas do 1o lote

    # 2o lote, separado, com horario totalmente novo -- a equipe ja usou as
    # duas arenas, entao o ciclo reseta e ela pode cair em qualquer uma,
    # mas a rotacao deve ter considerado o historico (nao ha erro nem
    # travamento) e o novo horario nao depende do lote anterior.
    resultado_3 = await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada3.id],
        datetime(2026, 8, 10, 14, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )
    assert resultado_3[0].horario_inicio == datetime(2026, 8, 10, 14, 0, tzinfo=UTC)
    assert resultado_3[0].arena_id in (arena_a.id, arena_b.id)


async def test_gerar_agendamentos_nao_repete_arena_antes_de_esgotar_elegiveis(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1], qtd_rodadas=3)
    rodada1 = await _criar_rodada(db_session, modalidade, 1)
    rodada2 = await _criar_rodada(db_session, modalidade, 2)

    arena_a = await _criar_arena(db_session, modalidade, nome="Arena A")
    arena_b = await _criar_arena(db_session, modalidade, nome="Arena B")
    arena_c = await _criar_arena(db_session, modalidade, nome="Arena C")
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe Solo", nivel=1)

    await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada1.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )
    arena_rodada1 = (await _agendamentos_da_rodada(db_session, rodada1.id))[0].arena_id

    await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada2.id],
        datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )
    arena_rodada2 = (await _agendamentos_da_rodada(db_session, rodada2.id))[0].arena_id

    assert arena_rodada2 != arena_rodada1
    assert {arena_rodada1, arena_rodada2}.issubset({arena_a.id, arena_b.id, arena_c.id})


async def test_gerar_agendamentos_encadeia_horario_da_proxima_rodada_no_mesmo_lote(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, niveis_aplicaveis=[1], duracao_maxima_rodada_seg=300, pausa_entre_rodadas_seg=60
    )
    rodada1 = await _criar_rodada(db_session, modalidade, 1)
    rodada2 = await _criar_rodada(db_session, modalidade, 2)
    await _criar_arena(db_session, modalidade, nome="Arena A")

    for i in range(3):
        await _criar_equipe_inscrita(
            db_session, modalidade, coordenador, nome=f"Equipe {i}", nivel=1
        )

    inicio = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    await gerar_agendamentos(
        db_session, modalidade.id, [rodada1.id, rodada2.id], inicio, usuario_id=coordenador.id
    )

    rodada2_atualizada = await db_session.get(Rodada, rodada2.id)
    # 3 equipes, 1 arena -> fila de 3 -> 3*300 + 60 de pausa
    assert rodada2_atualizada.horario_inicio == inicio + timedelta(seconds=3 * 300 + 60)


async def test_gerar_agendamentos_recusa_regerar_sem_flag(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1])
    rodada = await _criar_rodada(db_session, modalidade, 1)
    await _criar_arena(db_session, modalidade, nome="Arena A")
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe 1", nivel=1)

    await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await gerar_agendamentos(
            db_session,
            modalidade.id,
            [rodada.id],
            datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "AGENDAMENTO_JA_EXISTE"


async def test_gerar_agendamentos_regenerar_true_sobrescreve(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1])
    rodada = await _criar_rodada(db_session, modalidade, 1)
    await _criar_arena(db_session, modalidade, nome="Arena A")
    await _criar_equipe_inscrita(db_session, modalidade, coordenador, nome="Equipe 1", nivel=1)

    await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )
    novo_horario = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    resultado = await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada.id],
        novo_horario,
        usuario_id=coordenador.id,
        regenerar=True,
    )

    assert len(resultado) == 1
    assert resultado[0].horario_inicio == novo_horario
    agendamentos = await _agendamentos_da_rodada(db_session, rodada.id)
    assert len(agendamentos) == 1


async def test_gerar_agendamentos_erro_modalidade_nao_individual(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, tipo_disputa=TipoDisputa.CONFRONTO)
    rodada = await _criar_rodada(db_session, modalidade, 1)

    with pytest.raises(AppError) as exc_info:
        await gerar_agendamentos(
            db_session,
            modalidade.id,
            [rodada.id],
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "MODALIDADE_NAO_E_INDIVIDUAL"


async def test_gerar_agendamentos_erro_duracao_nao_configurada(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, duracao_maxima_rodada_seg=None)
    rodada = await _criar_rodada(db_session, modalidade, 1)

    with pytest.raises(AppError) as exc_info:
        await gerar_agendamentos(
            db_session,
            modalidade.id,
            [rodada.id],
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "DURACAO_RODADA_NAO_CONFIGURADA"


async def test_gerar_agendamentos_erro_sem_arenas_cadastradas(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    rodada = await _criar_rodada(db_session, modalidade, 1)

    with pytest.raises(AppError) as exc_info:
        await gerar_agendamentos(
            db_session,
            modalidade.id,
            [rodada.id],
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "ARENAS_NAO_CADASTRADAS"


async def test_gerar_agendamentos_erro_rodada_de_outra_modalidade(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade_a = await _criar_modalidade(db_session)
    modalidade_b = await _criar_modalidade(db_session)
    rodada_b = await _criar_rodada(db_session, modalidade_b, 1)
    await _criar_arena(db_session, modalidade_a, nome="Arena A")

    with pytest.raises(AppError) as exc_info:
        await gerar_agendamentos(
            db_session,
            modalidade_a.id,
            [rodada_b.id],
            datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "RODADA_NAO_PERTENCE_A_MODALIDADE"


async def test_gerar_agendamentos_balanceia_carga_entre_arenas(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1])
    rodada = await _criar_rodada(db_session, modalidade, 1)
    await _criar_arena(db_session, modalidade, nome="Arena A")
    await _criar_arena(db_session, modalidade, nome="Arena B")
    await _criar_arena(db_session, modalidade, nome="Arena C")

    for i in range(10):
        await _criar_equipe_inscrita(
            db_session, modalidade, coordenador, nome=f"Equipe {i}", nivel=1
        )

    resultado = await gerar_agendamentos(
        db_session,
        modalidade.id,
        [rodada.id],
        datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        usuario_id=coordenador.id,
    )

    contagem: dict = {}
    for agendamento in resultado:
        contagem[agendamento.arena_id] = contagem.get(agendamento.arena_id, 0) + 1

    assert len(resultado) == 10
    assert max(contagem.values()) - min(contagem.values()) <= 1
