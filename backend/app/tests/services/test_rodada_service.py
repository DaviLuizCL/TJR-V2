import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.rodada import ModoHorario, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.rodada import RodadaCreate, RodadaUpdate
from app.services.rodada import (
    atualizar_rodada,
    criar_rodada,
    listar_rodadas,
    obter_rodada,
)


async def _criar_coordenador(db_session, email="coord-rodada-service@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(db_session, *, qtd_rodadas=3, nome="Modalidade Teste") -> Modalidade:
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
        nome=nome,
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=qtd_rodadas,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


def _payload(modalidade_id, **overrides):
    base = dict(
        modalidade_id=modalidade_id,
        numero=1,
        modo_horario=ModoHorario.MANUAL,
        horario_inicio=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    )
    base.update(overrides)
    return RodadaCreate(**base)


async def test_criar_rodada_nasce_agendada(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)

    rodada = await criar_rodada(db_session, _payload(modalidade.id), usuario_id=coordenador.id)

    assert rodada.status == RodadaStatus.AGENDADA
    assert rodada.numero == 1


async def test_criar_rodada_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)

    rodada = await criar_rodada(db_session, _payload(modalidade.id), usuario_id=coordenador.id)

    resultado = await db_session.execute(select(AuditLog).where(AuditLog.entidade_id == rodada.id))
    log = resultado.scalar_one()
    assert log.entidade == "rodada"
    assert log.acao == "CRIAR"


async def test_criar_rodada_com_modalidade_inexistente_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_rodada(db_session, _payload(uuid.uuid4()), usuario_id=coordenador.id)

    assert exc_info.value.codigo == "MODALIDADE_NAO_ENCONTRADA"


async def test_criar_rodada_com_numero_fora_do_intervalo_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, qtd_rodadas=2)

    with pytest.raises(AppError) as exc_info:
        await criar_rodada(db_session, _payload(modalidade.id, numero=3), usuario_id=coordenador.id)

    assert exc_info.value.codigo == "NUMERO_RODADA_INVALIDO"


async def test_criar_rodada_com_numero_duplicado_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    await criar_rodada(db_session, _payload(modalidade.id, numero=1), usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await criar_rodada(db_session, _payload(modalidade.id, numero=1), usuario_id=coordenador.id)

    assert exc_info.value.codigo == "RODADA_NUMERO_DUPLICADO"


async def test_criar_rodada_manual_sem_horario_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_rodada(
            db_session,
            _payload(modalidade.id, horario_inicio=None),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "HORARIO_INICIO_OBRIGATORIO"


async def test_criar_rodada_automatica_pode_nascer_sem_horario(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)

    rodada = await criar_rodada(
        db_session,
        _payload(modalidade.id, modo_horario=ModoHorario.AUTOMATICO, horario_inicio=None),
        usuario_id=coordenador.id,
    )

    assert rodada.horario_inicio is None


async def test_obter_rodada_inexistente_lanca_erro(db_session):
    with pytest.raises(AppError) as exc_info:
        await obter_rodada(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "RODADA_NAO_ENCONTRADA"


async def test_listar_rodadas_filtra_por_modalidade_e_ordena_por_numero(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, qtd_rodadas=3)
    await criar_rodada(db_session, _payload(modalidade.id, numero=2), usuario_id=coordenador.id)
    await criar_rodada(db_session, _payload(modalidade.id, numero=1), usuario_id=coordenador.id)

    itens, total = await listar_rodadas(db_session, modalidade_id=modalidade.id, page=1, size=50)

    assert total == 2
    assert [r.numero for r in itens] == [1, 2]


async def test_atualizar_rodada_altera_status_e_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    rodada = await criar_rodada(db_session, _payload(modalidade.id), usuario_id=coordenador.id)

    atualizada = await atualizar_rodada(
        db_session,
        rodada.id,
        RodadaUpdate(status=RodadaStatus.EM_ANDAMENTO),
        usuario_id=coordenador.id,
    )

    assert atualizada.status == RodadaStatus.EM_ANDAMENTO

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == rodada.id, AuditLog.acao == "ATUALIZAR")
    )
    log = resultado.scalar_one()
    assert log.depois["status"] == "EM_ANDAMENTO"


async def test_atualizar_rodada_para_manual_sem_horario_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session)
    rodada = await criar_rodada(
        db_session,
        _payload(modalidade.id, modo_horario=ModoHorario.AUTOMATICO, horario_inicio=None),
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await atualizar_rodada(
            db_session,
            rodada.id,
            RodadaUpdate(modo_horario=ModoHorario.MANUAL),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "HORARIO_INICIO_OBRIGATORIO"
