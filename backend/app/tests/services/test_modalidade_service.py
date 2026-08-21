import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.audit_log import AuditLog
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import (
    Consolidacao,
    DecisaoPartida,
    FormatoChaveamento,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.models.usuario import Papel, Usuario
from app.schemas.modalidade import ModalidadeCreate, ModalidadeUpdate
from app.services.modalidade import (
    atualizar_modalidade,
    criar_modalidade,
    listar_modalidades,
    obter_modalidade,
)


async def _criar_evento(db_session) -> Evento:
    evento = Evento(
        nome="TJR 2026",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento)
    await db_session.flush()
    return evento


async def _criar_coordenador(db_session) -> Usuario:
    usuario = Usuario(
        nome="Coordenador",
        email="coord-modalidade-service@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


def _payload(evento_id, **overrides):
    base = dict(
        evento_id=evento_id,
        nome="Sumo de Robos",
        tipo_disputa=TipoDisputa.CONFRONTO,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=3,
        consolidacao=Consolidacao.SOMA_RODADAS,
    )
    base.update(overrides)
    return ModalidadeCreate(**base)


async def test_criar_modalidade_nasce_em_rascunho(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    modalidade = await criar_modalidade(db_session, _payload(evento.id), usuario_id=coordenador.id)

    assert modalidade.status == ModalidadeStatus.RASCUNHO
    assert modalidade.evento_id == evento.id


async def test_criar_modalidade_grava_audit_log(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    modalidade = await criar_modalidade(db_session, _payload(evento.id), usuario_id=coordenador.id)

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == modalidade.id)
    )
    log = resultado.scalar_one()
    assert log.entidade == "modalidade"
    assert log.acao == "CRIAR"


async def test_criar_modalidade_com_evento_inexistente_lanca_erro(db_session):
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(db_session, _payload(uuid.uuid4()), usuario_id=coordenador.id)

    assert exc_info.value.codigo == "EVENTO_NAO_ENCONTRADO"


async def test_criar_modalidade_rejeita_nivel_fora_do_intervalo(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session, _payload(evento.id, niveis_aplicaveis=[0, 5]), usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "NIVEIS_APLICAVEIS_INVALIDOS"


async def test_criar_modalidade_rejeita_niveis_duplicados(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session, _payload(evento.id, niveis_aplicaveis=[1, 1]), usuario_id=coordenador.id
        )

    assert exc_info.value.codigo == "NIVEIS_APLICAVEIS_INVALIDOS"


async def test_criar_modalidade_rejeita_formato_chaveamento_em_individual(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session,
            _payload(
                evento.id, tipo_disputa=TipoDisputa.INDIVIDUAL, formato_chaveamento="MATA_MATA"
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "FORMATO_CHAVEAMENTO_APENAS_CONFRONTO"


async def test_criar_modalidade_confronto_pode_ter_formato_chaveamento_nulo(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    modalidade = await criar_modalidade(
        db_session,
        _payload(evento.id, tipo_disputa=TipoDisputa.CONFRONTO, formato_chaveamento=None),
        usuario_id=coordenador.id,
    )

    assert modalidade.formato_chaveamento is None


async def test_criar_modalidade_melhor_n_rodadas_exige_consolidacao_n(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session,
            _payload(evento.id, consolidacao=Consolidacao.MELHOR_N_RODADAS, consolidacao_n=None),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CONSOLIDACAO_N_OBRIGATORIO"


async def test_criar_modalidade_consolidacao_n_nao_pode_exceder_qtd_rodadas(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session,
            _payload(
                evento.id,
                qtd_rodadas=2,
                consolidacao=Consolidacao.MELHOR_N_RODADAS,
                consolidacao_n=3,
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CONSOLIDACAO_N_MAIOR_QUE_QTD_RODADAS"


async def test_criar_modalidade_desempate_tipo_invalido(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session,
            _payload(
                evento.id,
                desempates=[{"tipo": "NAO_EXISTE", "criterio_id": None, "direcao": "MAIOR"}],
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "DESEMPATE_INVALIDO"


async def test_criar_modalidade_desempate_maior_pontuacao_exige_criterio_id(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    with pytest.raises(AppError) as exc_info:
        await criar_modalidade(
            db_session,
            _payload(
                evento.id,
                desempates=[
                    {"tipo": "MAIOR_PONTUACAO_NO_CRITERIO", "criterio_id": None, "direcao": "MAIOR"}
                ],
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "DESEMPATE_INVALIDO"


async def test_criar_modalidade_desempate_valido_e_persistido(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)
    desempates = [
        {"tipo": "MAIOR_TOTAL_EM_UMA_RODADA", "criterio_id": None, "direcao": "MAIOR"},
        {"tipo": "MENOR_TEMPO", "criterio_id": None, "direcao": "MENOR"},
    ]

    modalidade = await criar_modalidade(
        db_session, _payload(evento.id, desempates=desempates), usuario_id=coordenador.id
    )

    assert modalidade.desempates == desempates


async def test_obter_modalidade_inexistente_lanca_erro(db_session):
    with pytest.raises(AppError) as exc_info:
        await obter_modalidade(db_session, uuid.uuid4())

    assert exc_info.value.codigo == "MODALIDADE_NAO_ENCONTRADA"


async def test_listar_modalidades_filtra_por_evento(db_session):
    evento_a = await _criar_evento(db_session)
    evento_b = Evento(
        nome="TJR 2027",
        ano=2027,
        data_inicio=date(2027, 3, 10),
        data_fim=date(2027, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db_session.add(evento_b)
    await db_session.flush()
    coordenador = await _criar_coordenador(db_session)

    await criar_modalidade(db_session, _payload(evento_a.id, nome="M1"), usuario_id=coordenador.id)
    await criar_modalidade(db_session, _payload(evento_a.id, nome="M2"), usuario_id=coordenador.id)
    await criar_modalidade(db_session, _payload(evento_b.id, nome="M3"), usuario_id=coordenador.id)

    itens, total = await listar_modalidades(db_session, evento_id=evento_a.id, page=1, size=50)

    assert total == 2
    assert {m.nome for m in itens} == {"M1", "M2"}


async def test_atualizar_modalidade_altera_campos_e_grava_audit_log(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)
    modalidade = await criar_modalidade(db_session, _payload(evento.id), usuario_id=coordenador.id)

    atualizada = await atualizar_modalidade(
        db_session,
        modalidade.id,
        ModalidadeUpdate(nome="Sumo Avancado"),
        usuario_id=coordenador.id,
    )

    assert atualizada.nome == "Sumo Avancado"

    resultado = await db_session.execute(
        select(AuditLog).where(AuditLog.entidade_id == modalidade.id, AuditLog.acao == "ATUALIZAR")
    )
    log = resultado.scalar_one()
    assert log.antes["nome"] == "Sumo de Robos"
    assert log.depois["nome"] == "Sumo Avancado"


async def test_pausa_entre_rodadas_seg_e_criada_e_atualizada(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)
    modalidade = await criar_modalidade(
        db_session, _payload(evento.id, pausa_entre_rodadas_seg=60), usuario_id=coordenador.id
    )

    assert modalidade.pausa_entre_rodadas_seg == 60

    atualizada = await atualizar_modalidade(
        db_session,
        modalidade.id,
        ModalidadeUpdate(pausa_entre_rodadas_seg=120),
        usuario_id=coordenador.id,
    )

    assert atualizada.pausa_entre_rodadas_seg == 120


async def test_atualizar_modalidade_revalida_regras_com_estado_final(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)
    modalidade = await criar_modalidade(
        db_session, _payload(evento.id, qtd_rodadas=5), usuario_id=coordenador.id
    )

    with pytest.raises(AppError) as exc_info:
        await atualizar_modalidade(
            db_session,
            modalidade.id,
            ModalidadeUpdate(
                qtd_rodadas=1, consolidacao=Consolidacao.MELHOR_N_RODADAS, consolidacao_n=3
            ),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "CONSOLIDACAO_N_MAIOR_QUE_QTD_RODADAS"


async def test_atualizar_modalidade_recusa_mudar_formato_chaveamento_apos_rodada_criada(
    db_session,
):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)
    modalidade = await criar_modalidade(
        db_session,
        _payload(evento.id, formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS),
        usuario_id=coordenador.id,
    )
    db_session.add(
        Rodada(
            modalidade_id=modalidade.id,
            numero=1,
            modo_horario=ModoHorario.MANUAL,
            status=RodadaStatus.AGENDADA,
        )
    )
    await db_session.flush()

    with pytest.raises(AppError) as exc_info:
        await atualizar_modalidade(
            db_session,
            modalidade.id,
            ModalidadeUpdate(formato_chaveamento=FormatoChaveamento.MATA_MATA),
            usuario_id=coordenador.id,
        )

    assert exc_info.value.codigo == "FORMATO_CHAVEAMENTO_TRAVADO"


async def test_atualizar_modalidade_permite_mudar_formato_chaveamento_sem_rodada(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)
    modalidade = await criar_modalidade(
        db_session,
        _payload(evento.id, formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS),
        usuario_id=coordenador.id,
    )

    atualizada = await atualizar_modalidade(
        db_session,
        modalidade.id,
        ModalidadeUpdate(formato_chaveamento=FormatoChaveamento.MATA_MATA),
        usuario_id=coordenador.id,
    )

    assert atualizada.formato_chaveamento == FormatoChaveamento.MATA_MATA


async def test_criar_modalidade_default_decisao_partida_e_combates_vencidos(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    modalidade = await criar_modalidade(db_session, _payload(evento.id), usuario_id=coordenador.id)

    assert modalidade.decisao_partida == DecisaoPartida.COMBATES_VENCIDOS


async def test_criar_modalidade_aceita_decisao_partida_soma_pontos(db_session):
    evento = await _criar_evento(db_session)
    coordenador = await _criar_coordenador(db_session)

    modalidade = await criar_modalidade(
        db_session,
        _payload(evento.id, decisao_partida=DecisaoPartida.SOMA_PONTOS),
        usuario_id=coordenador.id,
    )

    assert modalidade.decisao_partida == DecisaoPartida.SOMA_PONTOS
