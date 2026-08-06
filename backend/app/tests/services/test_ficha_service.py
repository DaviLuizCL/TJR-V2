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
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.ficha import FichaCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services.ficha import (
    criar_ficha,
    depreciar_ficha,
    excluir_ficha,
    listar_fichas,
    obter_ficha,
    obter_ficha_completa,
    publicar_ficha,
)
from app.services.lancamento import criar_lancamento


async def _criar_coordenador(db_session) -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email="coord-ficha-service@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade(db_session, *, ficha_unica_entre_niveis, niveis_aplicaveis=None):
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
        niveis_aplicaveis=niveis_aplicaveis or [1, 2],
        ficha_unica_entre_niveis=ficha_unica_entre_niveis,
        qtd_rodadas=3,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def test_criar_ficha_com_nivel_para_modalidade_multi_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)

    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )

    assert ficha.nivel == 1
    assert ficha.versao == 1
    assert ficha.status == FichaStatus.RASCUNHO


async def test_criar_ficha_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)

    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )

    resultado = await db_session.execute(select(AuditLog).where(AuditLog.entidade_id == ficha.id))
    log = resultado.scalar_one()
    assert log.entidade == "ficha"
    assert log.acao == "CRIAR"


async def test_criar_ficha_sem_nivel_quando_obrigatorio_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)

    with pytest.raises(AppError) as exc_info:
        await criar_ficha(
            db_session,
            FichaCreate(modalidade_id=modalidade.id, nivel=None),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "FICHA_NIVEL_OBRIGATORIO"


async def test_criar_ficha_com_nivel_quando_ficha_unica_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=True)

    with pytest.raises(AppError) as exc_info:
        await criar_ficha(
            db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "FICHA_NIVEL_NAO_PERMITIDO"


async def test_criar_ficha_com_nivel_fora_dos_aplicaveis_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, ficha_unica_entre_niveis=False, niveis_aplicaveis=[1, 2]
    )

    with pytest.raises(AppError) as exc_info:
        await criar_ficha(
            db_session, FichaCreate(modalidade_id=modalidade.id, nivel=3), usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "FICHA_NIVEL_FORA_DOS_APLICAVEIS"


async def test_criar_ficha_duplicada_para_mesmo_nivel_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )

    with pytest.raises(AppError) as exc_info:
        await criar_ficha(
            db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "FICHA_JA_EXISTE_PARA_NIVEL"


async def test_criar_ficha_unica_com_nivel_nulo_funciona(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=True)

    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=None), usuario_id=coordenador.id
    )

    assert ficha.nivel is None


async def test_obter_ficha_inexistente_lanca_erro(db_session):
    with pytest.raises(AppError) as exc_info:
        await obter_ficha(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "FICHA_NAO_ENCONTRADA"
    assert exc_info.value.status_code == 404


async def test_listar_fichas_filtra_por_modalidade_e_nivel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=2), usuario_id=coordenador.id
    )

    itens, total = await listar_fichas(
        db_session, modalidade_id=modalidade.id, nivel=1, page=1, size=50
    )

    assert total == 1
    assert itens[0].nivel == 1


async def test_publicar_ficha_define_status_e_publicada_em(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )

    publicada = await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert publicada.status == FichaStatus.PUBLICADA
    assert publicada.publicada_em is not None


async def test_publicar_ficha_ja_publicada_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "FICHA_NAO_PODE_SER_PUBLICADA"


async def _criar_lancamento_para_ficha(db_session, ficha, *, arbitro=None):
    modalidade = await db_session.get(Modalidade, ficha.modalidade_id)
    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
        ativo=True,
    )
    db_session.add(criterio)
    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db_session.add(rodada)
    equipe = Equipe(nome="Equipe A", nivel=1)
    db_session.add(equipe)
    if arbitro is None:
        arbitro = Usuario(
            nome="Arbitro",
            email="arbitro-ficha-service@tjr.app",
            senha_hash=hash_senha("senha-123"),
            papel=Papel.ARBITRO,
        )
        db_session.add(arbitro)
    await db_session.flush()

    payload = LancamentoCreate(
        ficha_id=ficha.id,
        rodada_id=rodada.id,
        tentativa=1,
        equipe_id=equipe.id,
        client_operation_id=uuid.uuid4(),
        itens=[ItemLancamentoInput(criterio_id=criterio.id, ocorrencias=1)],
    )
    return await criar_lancamento(db_session, payload, arbitro_id=arbitro.id)


async def test_excluir_ficha_sem_lancamentos_remove_do_banco(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    grupo = Grupo(ficha_id=ficha.id, nome="Geral", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    await excluir_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert await db_session.get(Ficha, ficha.id) is None
    resultado = await db_session.execute(select(Grupo).where(Grupo.ficha_id == ficha.id))
    assert resultado.scalars().all() == []


async def test_excluir_ficha_com_lancamentos_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(
        db_session, ficha_unica_entre_niveis=False, niveis_aplicaveis=[1]
    )
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    await _criar_lancamento_para_ficha(db_session, ficha)

    with pytest.raises(AppError) as exc_info:
        await excluir_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "FICHA_POSSUI_LANCAMENTOS"
    assert exc_info.value.status_code == 409
    assert await db_session.get(Ficha, ficha.id) is not None


async def test_depreciar_ficha_publicada_marca_status(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    await _criar_lancamento_para_ficha(db_session, ficha)

    depreciada = await depreciar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert depreciada.status == FichaStatus.DEPRECADA


async def test_depreciar_ficha_rascunho_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )

    with pytest.raises(AppError) as exc_info:
        await depreciar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "FICHA_RASCUNHO_NAO_PODE_SER_DEPRECIADA"


async def test_depreciar_ficha_ja_depreciada_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)
    await depreciar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await depreciar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "FICHA_JA_DEPRECIADA"


async def test_depreciar_ficha_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    await publicar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    await depreciar_ficha(db_session, ficha.id, usuario_id=coordenador.id)

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == ficha.id, AuditLog.acao == "DEPRECIAR")
    )
    log = resultado.scalar_one()
    assert log.entidade == "ficha"


async def test_obter_ficha_completa_monta_grupos_e_criterios_aninhados(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade(db_session, ficha_unica_entre_niveis=False)
    ficha = await criar_ficha(
        db_session, FichaCreate(modalidade_id=modalidade.id, nivel=1), usuario_id=coordenador.id
    )
    grupo = Grupo(ficha_id=ficha.id, nome="Parte Tecnica", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    completa = await obter_ficha_completa(db_session, ficha.id)

    assert len(completa.grupos) == 1
    assert completa.grupos[0].nome == "Parte Tecnica"
    assert completa.grupos[0].criterios == []
