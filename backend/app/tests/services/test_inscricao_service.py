import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.usuario import Papel, Usuario
from app.schemas.inscricao import InscricaoCreate
from app.services.inscricao import criar_inscricao, listar_inscricoes, obter_inscricao


async def _criar_coordenador(db_session, email="coord-inscricao-service@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_equipe(db_session, nome="Equipe A", nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    return equipe


async def _criar_modalidade(
    db_session, *, niveis_aplicaveis, nome="Modalidade Teste"
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
        nome=nome,
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=niveis_aplicaveis,
        ficha_unica_entre_niveis=False,
        qtd_rodadas=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def test_criar_inscricao_vincula_equipe_e_modalidade(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])
    equipe = await _criar_equipe(db_session, nivel=1)

    inscricao = await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )

    assert inscricao.equipe_id == equipe.id
    assert inscricao.modalidade_id == modalidade.id


async def test_criar_inscricao_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])
    equipe = await _criar_equipe(db_session, nivel=1)

    inscricao = await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == inscricao.id)
    )
    log = resultado.scalar_one()
    assert log.entidade == "inscricao"
    assert log.acao == "CRIAR"


async def test_criar_inscricao_com_equipe_inexistente_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])

    with pytest.raises(AppError) as exc_info:
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=uuid.uuid4(), modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "EQUIPE_NAO_ENCONTRADA"


async def test_criar_inscricao_com_modalidade_inexistente_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    equipe = await _criar_equipe(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=uuid.uuid4()),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "MODALIDADE_NAO_ENCONTRADA"


async def test_criar_inscricao_com_nivel_incompativel_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])
    equipe = await _criar_equipe(db_session, nivel=3)

    with pytest.raises(AppError) as exc_info:
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "NIVEL_EQUIPE_INCOMPATIVEL"


async def test_criar_inscricao_duplicada_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, niveis_aplicaveis=[1, 2])
    equipe = await _criar_equipe(db_session, nivel=1)
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await criar_inscricao(
            db_session,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "INSCRICAO_DUPLICADA"


async def test_obter_inscricao_inexistente_lanca_erro(db_session):
    with pytest.raises(AppError) as exc_info:
        await obter_inscricao(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "INSCRICAO_NAO_ENCONTRADA"


async def test_listar_inscricoes_filtra_por_modalidade(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade_a = await _criar_modalidade(db_session, niveis_aplicaveis=[1], nome="Modalidade A")
    modalidade_b = await _criar_modalidade(db_session, niveis_aplicaveis=[1], nome="Modalidade B")
    equipe_a = await _criar_equipe(db_session, nome="A", nivel=1)
    equipe_b = await _criar_equipe(db_session, nome="B", nivel=1)

    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe_a.id, modalidade_id=modalidade_a.id),
        usuario_id=coordenador.id,
    )
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe_b.id, modalidade_id=modalidade_b.id),
        usuario_id=coordenador.id,
    )

    itens, total = await listar_inscricoes(
        db_session, modalidade_id=modalidade_a.id, equipe_id=None, page=1, size=50
    )

    assert total == 1
    assert itens[0].equipe_id == equipe_a.id
