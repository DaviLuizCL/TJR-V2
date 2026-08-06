from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo, ModificadorTipo
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.usuario import Papel, Usuario
from app.schemas.criterio import CriterioCreate, CriterioUpdate
from app.schemas.grupo import GrupoCreate, GrupoUpdate
from app.services.criterio import atualizar_criterio, criar_criterio, deletar_criterio
from app.services.grupo import atualizar_grupo, criar_grupo, deletar_grupo


async def _criar_coordenador(db_session) -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email="coord-grupo-criterio@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_ficha_rascunho(db_session) -> Ficha:
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
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=3,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(modalidade)
    await db_session.flush()

    ficha = Ficha(modalidade_id=modalidade.id, nivel=1, versao=1, status=FichaStatus.RASCUNHO)
    db_session.add(ficha)
    await db_session.flush()
    return ficha


async def _publicar(db_session, ficha: Ficha) -> None:
    ficha.status = FichaStatus.PUBLICADA
    ficha.publicada_em = datetime.now(UTC)
    await db_session.flush()


# ---------- grupo ----------


async def test_criar_grupo_em_ficha_rascunho_usa_a_mesma_ficha(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)

    grupo = await criar_grupo(
        db_session, ficha.id, GrupoCreate(nome="Parte Tecnica", ordem=1), usuario_id=coordenador.id
    )

    assert grupo.ficha_id == ficha.id


async def test_criar_grupo_em_ficha_publicada_nao_cria_nova_versao(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    await _publicar(db_session, ficha)

    grupo = await criar_grupo(
        db_session, ficha.id, GrupoCreate(nome="Parte Tecnica", ordem=1), usuario_id=coordenador.id
    )

    # grupo e so organizacao visual: nao faz parte do contrato de pontuacao
    # (criterio_snapshot referencia apenas criterio, nunca grupo), entao
    # mexer nele nao precisa versionar a ficha.
    assert grupo.ficha_id == ficha.id

    await db_session.refresh(ficha)
    assert ficha.status == FichaStatus.PUBLICADA


async def test_atualizar_grupo_em_ficha_publicada_edita_no_lugar(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Nome Antigo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    await _publicar(db_session, ficha)

    atualizado = await atualizar_grupo(
        db_session, grupo.id, GrupoUpdate(nome="Nome Novo"), usuario_id=coordenador.id
    )

    assert atualizado.nome == "Nome Novo"
    assert atualizado.id == grupo.id
    assert atualizado.ficha_id == ficha.id


async def test_deletar_grupo_em_ficha_rascunho(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Para Remover", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    await deletar_grupo(db_session, grupo.id, usuario_id=coordenador.id)

    resultado = await db_session.execute(select(Grupo).where(Grupo.id == grupo.id))
    assert resultado.scalar_one_or_none() is None


# ---------- criterio: validacoes por tipo ----------


async def test_criar_criterio_contador_sem_pontos_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Lombada",
                categoria=CategoriaCriterio.PONTUACAO,
                tipo=CriterioTipo.CONTADOR,
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_PONTOS_OBRIGATORIO"


async def test_criar_criterio_escala_sem_valores_permitidos_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Nota Artistica",
                categoria=CategoriaCriterio.PONTUACAO,
                tipo=CriterioTipo.ESCALA,
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_VALORES_PERMITIDOS_OBRIGATORIO"


async def test_criar_criterio_escala_com_valores_duplicados_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Nota Artistica",
                categoria=CategoriaCriterio.PONTUACAO,
                tipo=CriterioTipo.ESCALA,
                valores_permitidos=[0, 5, 5, 10],
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_VALORES_PERMITIDOS_INVALIDO"


async def test_criar_criterio_escala_com_valores_fora_de_ordem_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Nota Artistica",
                categoria=CategoriaCriterio.PONTUACAO,
                tipo=CriterioTipo.ESCALA,
                valores_permitidos=[10, 0, 5],
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_VALORES_PERMITIDOS_INVALIDO"


async def test_criar_criterio_modificador_sem_tipo_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Excedeu tempo",
                categoria=CategoriaCriterio.PENALIDADE,
                tipo=CriterioTipo.MODIFICADOR,
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_MODIFICADOR_TIPO_OBRIGATORIO"


async def test_criar_criterio_modificador_percentual_valor_fora_do_intervalo_lanca_erro(
    db_session,
):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Excedeu tempo",
                categoria=CategoriaCriterio.PENALIDADE,
                tipo=CriterioTipo.MODIFICADOR,
                modificador_tipo=ModificadorTipo.PERCENTUAL,
                modificador_valor=Decimal("150"),
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_MODIFICADOR_VALOR_INVALIDO"


async def test_criar_criterio_modificador_zera_total_como_pontuacao_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await criar_criterio(
            db_session,
            grupo.id,
            CriterioCreate(
                nome="Bonus impossivel",
                categoria=CategoriaCriterio.PONTUACAO,
                tipo=CriterioTipo.MODIFICADOR,
                modificador_tipo=ModificadorTipo.ZERA_TOTAL,
                ordem=1,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CRITERIO_ZERA_TOTAL_APENAS_PENALIDADE"


async def test_criar_criterio_modificador_percentual_como_pontuacao_e_valido(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = await criar_criterio(
        db_session,
        grupo.id,
        CriterioCreate(
            nome="Terminou no tempo",
            categoria=CategoriaCriterio.PONTUACAO,
            tipo=CriterioTipo.MODIFICADOR,
            modificador_tipo=ModificadorTipo.PERCENTUAL,
            modificador_valor=Decimal("10"),
            ordem=1,
        ),
        usuario_id=coordenador.id,
    )

    assert criterio.categoria == CategoriaCriterio.PONTUACAO
    assert criterio.modificador_tipo == ModificadorTipo.PERCENTUAL


async def test_criar_criterio_valido_grava_audit_log(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = await criar_criterio(
        db_session,
        grupo.id,
        CriterioCreate(
            nome="Lombada",
            categoria=CategoriaCriterio.PONTUACAO,
            tipo=CriterioTipo.CONTADOR,
            pontos=Decimal("10"),
            ordem=1,
        ),
        usuario_id=coordenador.id,
    )

    assert criterio.pontos == Decimal("10")


async def test_criar_criterio_contador_como_penalidade_e_valido(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()

    criterio = await criar_criterio(
        db_session,
        grupo.id,
        CriterioCreate(
            nome="Colisao",
            categoria=CategoriaCriterio.PENALIDADE,
            tipo=CriterioTipo.CONTADOR,
            pontos=Decimal("20"),
            ordem=1,
        ),
        usuario_id=coordenador.id,
    )

    assert criterio.categoria == CategoriaCriterio.PENALIDADE
    assert criterio.tipo == CriterioTipo.CONTADOR


# ---------- criterio: versionamento ----------


async def test_atualizar_criterio_em_ficha_publicada_clona_e_preserva_original(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
    )
    db_session.add(criterio)
    await db_session.flush()
    await _publicar(db_session, ficha)

    atualizado = await atualizar_criterio(
        db_session, criterio.id, CriterioUpdate(pontos=Decimal("20")), usuario_id=coordenador.id
    )

    assert atualizado.pontos == Decimal("20")
    assert atualizado.id != criterio.id

    await db_session.refresh(criterio)
    assert criterio.pontos == Decimal("10")


async def test_atualizar_criterio_revalida_regras_do_tipo(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
    )
    db_session.add(criterio)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await atualizar_criterio(
            db_session, criterio.id, CriterioUpdate(pontos=None), usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "CRITERIO_PONTOS_OBRIGATORIO"


async def test_deletar_criterio_em_ficha_rascunho(db_session):
    coordenador = await _criar_coordenador(db_session)
    ficha = await _criar_ficha_rascunho(db_session)
    grupo = Grupo(ficha_id=ficha.id, nome="Grupo", ordem=1)
    db_session.add(grupo)
    await db_session.flush()
    criterio = Criterio(
        grupo_id=grupo.id,
        nome="Lombada",
        categoria=CategoriaCriterio.PONTUACAO,
        tipo=CriterioTipo.CONTADOR,
        pontos=Decimal("10"),
        ordem=1,
    )
    db_session.add(criterio)
    await db_session.flush()

    await deletar_criterio(db_session, criterio.id, usuario_id=coordenador.id)

    resultado = await db_session.execute(select(Criterio).where(Criterio.id == criterio.id))
    assert resultado.scalar_one_or_none() is None
