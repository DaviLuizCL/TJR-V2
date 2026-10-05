from datetime import date

import pytest

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.usuario import Papel, Usuario
from app.schemas.chave import ChaveCreate
from app.schemas.inscricao import InscricaoCreate
from app.services.chave import (
    adicionar_equipe,
    criar_chave,
    listar_chaves,
    remover_equipe,
)
from app.services.chaveamento import criar_partida_manual
from app.services.inscricao import criar_inscricao


async def _criar_coordenador(db_session, email="coord-chave@tjr.app") -> Usuario:
    usuario = Usuario(
        nome="Coordenador", email=email, senha_hash=hash_senha("senha-123"), papel=Papel.COORDENADOR
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _criar_modalidade_confronto(
    db_session, *, nome="Combate", niveis_aplicaveis=None
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
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=None,
        niveis_aplicaveis=niveis_aplicaveis or [1, 2],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=5,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade)
    await db_session.flush()
    return modalidade


async def _inscrever(db_session, modalidade, coordenador, nome, nivel=1) -> Equipe:
    equipe = Equipe(nome=nome, nivel=nivel)
    db_session.add(equipe)
    await db_session.flush()
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
        usuario_id=coordenador.id,
    )
    return equipe


async def test_criar_chave_recusa_modalidade_nao_confronto(db_session):
    coordenador = await _criar_coordenador(db_session)
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
        await criar_chave(
            db_session,
            ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "MODALIDADE_NAO_E_CONFRONTO"


async def test_criar_chave_recusa_nivel_fora_dos_aplicaveis(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])

    with pytest.raises(AppError) as exc_info:
        await criar_chave(
            db_session,
            ChaveCreate(modalidade_id=modalidade.id, nivel=3, nome="Chave A"),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "NIVEL_FORA_DOS_APLICAVEIS"


async def test_criar_chave_com_nivel_aplicavel(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])

    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )

    assert chave.nome == "Chave A"
    assert chave.nivel == 1
    assert chave.modalidade_id == modalidade.id


async def test_adicionar_equipe_recusa_equipe_de_nivel_diferente(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session, niveis_aplicaveis=[1, 2])
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    equipe = await _inscrever(db_session, modalidade, coordenador, "Equipe Nivel 2", nivel=2)

    with pytest.raises(AppError) as exc_info:
        await adicionar_equipe(db_session, chave.id, equipe.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "NIVEIS_INCOMPATIVEIS"


async def test_adicionar_equipe_recusa_equipe_nao_inscrita(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    fora = Equipe(nome="Fora", nivel=1)
    db_session.add(fora)
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await adicionar_equipe(db_session, chave.id, fora.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "EQUIPE_NAO_INSCRITA"


async def test_adicionar_equipe_recusa_equipe_ja_em_outra_chave_da_mesma_modalidade(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    chave_a = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    chave_b = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave B"),
        usuario_id=coordenador.id,
    )
    equipe = await _inscrever(db_session, modalidade, coordenador, "Equipe 1")
    await adicionar_equipe(db_session, chave_a.id, equipe.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as exc_info:
        await adicionar_equipe(db_session, chave_b.id, equipe.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "EQUIPE_JA_TEM_CHAVE"


async def test_adicionar_equipe_permite_mesma_equipe_em_chaves_de_modalidades_diferentes(
    db_session,
):
    coordenador = await _criar_coordenador(db_session)
    modalidade_1 = await _criar_modalidade_confronto(db_session, nome="Cabo de Guerra")
    modalidade_2 = await _criar_modalidade_confronto(db_session, nome="Sumô")
    chave_1 = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade_1.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    chave_2 = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade_2.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    equipe = Equipe(nome="Equipe 1", nivel=1)
    db_session.add(equipe)
    await db_session.flush()
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade_1.id),
        usuario_id=coordenador.id,
    )
    await criar_inscricao(
        db_session,
        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade_2.id),
        usuario_id=coordenador.id,
    )

    await adicionar_equipe(db_session, chave_1.id, equipe.id, usuario_id=coordenador.id)
    await adicionar_equipe(db_session, chave_2.id, equipe.id, usuario_id=coordenador.id)

    _, equipes_1 = (await listar_chaves(db_session, modalidade_1.id))[0]
    _, equipes_2 = (await listar_chaves(db_session, modalidade_2.id))[0]
    assert equipes_1 == [equipe.id]
    assert equipes_2 == [equipe.id]


async def test_remover_equipe_rejeita_se_chave_ja_tem_partida(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    equipe_a = await _inscrever(db_session, modalidade, coordenador, "Equipe A")
    equipe_b = await _inscrever(db_session, modalidade, coordenador, "Equipe B")
    await adicionar_equipe(db_session, chave.id, equipe_a.id, usuario_id=coordenador.id)
    await adicionar_equipe(db_session, chave.id, equipe_b.id, usuario_id=coordenador.id)
    await criar_partida_manual(
        db_session,
        modalidade.id,
        equipe_a.id,
        equipe_b.id,
        rodada_numero=1,
        formato=FormatoChaveamento.TODOS_CONTRA_TODOS,
        usuario_id=coordenador.id,
    )

    with pytest.raises(AppError) as exc_info:
        await remover_equipe(db_session, chave.id, equipe_a.id, usuario_id=coordenador.id)

    assert exc_info.value.codigo == "CHAVE_JA_TEM_PARTIDA"


async def test_remover_equipe_ok_quando_chave_sem_partida(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    equipe = await _inscrever(db_session, modalidade, coordenador, "Equipe A")
    await adicionar_equipe(db_session, chave.id, equipe.id, usuario_id=coordenador.id)

    await remover_equipe(db_session, chave.id, equipe.id, usuario_id=coordenador.id)

    _, equipes = (await listar_chaves(db_session, modalidade.id))[0]
    assert equipes == []


async def test_listar_chaves_traz_equipes_associadas(db_session):
    coordenador = await _criar_coordenador(db_session)
    modalidade = await _criar_modalidade_confronto(db_session)
    chave = await criar_chave(
        db_session,
        ChaveCreate(modalidade_id=modalidade.id, nivel=1, nome="Chave A"),
        usuario_id=coordenador.id,
    )
    equipe_a = await _inscrever(db_session, modalidade, coordenador, "Equipe A")
    equipe_b = await _inscrever(db_session, modalidade, coordenador, "Equipe B")
    await adicionar_equipe(db_session, chave.id, equipe_a.id, usuario_id=coordenador.id)
    await adicionar_equipe(db_session, chave.id, equipe_b.id, usuario_id=coordenador.id)

    resultado = await listar_chaves(db_session, modalidade.id)

    assert len(resultado) == 1
    chave_obtida, equipe_ids = resultado[0]
    assert chave_obtida.id == chave.id
    assert set(equipe_ids) == {equipe_a.id, equipe_b.id}
