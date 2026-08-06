from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)


async def test_modalidade_aplica_defaults(db_session, evento):
    obj = Modalidade(
        evento_id=evento.id,
        nome="Sumo de Robos",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        niveis_aplicaveis=[1, 2],
        ficha_unica_entre_niveis=False,
        qtd_rodadas=3,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(obj)
    await db_session.flush()

    assert obj.tentativas_por_rodada == 1
    assert obj.permite_total_negativo is False
    assert obj.niveis_aplicaveis == [1, 2]
    assert obj.evento_id == evento.id


async def test_modalidade_aceita_desempates_em_jsonb(db_session, evento):
    desempates = [
        {"tipo": "MAIOR_TOTAL_EM_UMA_RODADA", "criterio_id": None, "direcao": "MAIOR"},
        {"tipo": "MENOR_TEMPO", "criterio_id": None, "direcao": "MENOR"},
    ]
    obj = Modalidade(
        evento_id=evento.id,
        nome="Danca",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        niveis_aplicaveis=[1, 2, 3, 4],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=1,
        consolidacao=Consolidacao.MELHOR_RODADA,
        status=ModalidadeStatus.RASCUNHO,
        desempates=desempates,
    )
    db_session.add(obj)
    await db_session.flush()
    await db_session.refresh(obj)

    assert obj.desempates == desempates


async def test_modalidade_individual_pode_ter_formato_chaveamento_nulo(db_session, evento):
    obj = Modalidade(
        evento_id=evento.id,
        nome="Resgate no Plano",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        formato_chaveamento=None,
        niveis_aplicaveis=[1],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=2,
        consolidacao=Consolidacao.MELHOR_N_RODADAS,
        consolidacao_n=1,
        status=ModalidadeStatus.RASCUNHO,
    )
    db_session.add(obj)
    await db_session.flush()

    assert obj.formato_chaveamento is None
