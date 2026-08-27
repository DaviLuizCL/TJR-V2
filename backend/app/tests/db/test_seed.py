from sqlalchemy import select

from app.core.security import verificar_senha
from app.db.seed import (
    EQUIPES_TJR,
    FICHA_VIAGEM_POR_NIVEL,
    FICHAS_TJR,
    MODALIDADES_TJR,
    seed_agendamentos,
    seed_arenas,
    seed_coordenador,
    seed_equipes,
    seed_equipes_credenciadas,
    seed_evento,
    seed_fichas,
    seed_inscricoes,
    seed_modalidades,
    seed_rodadas,
)
from app.models.agendamento import Agendamento
from app.models.arena import Arena
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo, ModificadorTipo
from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.inscricao import Inscricao
from app.models.modalidade import (
    Consolidacao,
    DecisaoPartida,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.partida import Partida
from app.models.rodada import Rodada
from app.models.usuario import Papel, Usuario
from app.services.rodada import _rodadas_necessarias


async def _criterios_da_modalidade(db_session, modalidades, nome_modalidade) -> list[Criterio]:
    modalidade = next(m for m in modalidades if m.nome == nome_modalidade)
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == modalidade.id))
    ficha = resultado.scalar_one()
    resultado_grupos = await db_session.execute(select(Grupo).where(Grupo.ficha_id == ficha.id))
    grupos = resultado_grupos.scalars().all()
    resultado_criterios = await db_session.execute(
        select(Criterio).where(Criterio.grupo_id.in_([g.id for g in grupos]))
    )
    return list(resultado_criterios.scalars().all())


async def _criterio_unico_da_modalidade(db_session, modalidades, nome_modalidade) -> Criterio:
    criterios = await _criterios_da_modalidade(db_session, modalidades, nome_modalidade)
    assert len(criterios) == 1
    return criterios[0]


async def test_seed_coordenador_cria_usuario_coordenador(db_session):
    await seed_coordenador(db_session, email="novo-coord@tjr.app", senha="senha-123")
    await db_session.flush()

    resultado = await db_session.execute(
        select(Usuario).where(Usuario.email == "novo-coord@tjr.app")
    )
    usuario = resultado.scalar_one()

    assert usuario.papel == Papel.COORDENADOR
    assert usuario.ativo is True
    assert verificar_senha("senha-123", usuario.senha_hash)


async def test_seed_coordenador_e_idempotente(db_session):
    await seed_coordenador(db_session, email="repetido@tjr.app", senha="senha-123")
    await seed_coordenador(db_session, email="repetido@tjr.app", senha="outra-senha")
    await db_session.flush()

    resultado = await db_session.execute(select(Usuario).where(Usuario.email == "repetido@tjr.app"))
    usuarios = resultado.scalars().all()

    assert len(usuarios) == 1


async def test_seed_equipes_cria_dez_por_nivel(db_session):
    equipes = await seed_equipes(db_session, por_nivel=10)
    await db_session.flush()

    assert len(equipes) == 40
    for nivel in (1, 2, 3, 4):
        do_nivel = [e for e in equipes if e.nivel == nivel]
        assert len(do_nivel) == 10


async def test_seed_equipes_nome_contem_nome_e_nivel(db_session):
    equipes = await seed_equipes(db_session, por_nivel=10)

    for equipe in equipes:
        assert str(equipe.nivel) in equipe.nome
        assert "Equipe" in equipe.nome


async def test_seed_equipes_e_idempotente(db_session):
    await seed_equipes(db_session, por_nivel=10)
    await db_session.flush()
    await seed_equipes(db_session, por_nivel=10)
    await db_session.flush()

    resultado = await db_session.execute(select(Equipe))
    equipes = resultado.scalars().all()

    assert len(equipes) == 40


async def test_seed_evento_cria_evento_tjr_2026(db_session):
    evento = await seed_evento(db_session)
    await db_session.flush()

    resultado = await db_session.execute(select(Evento).where(Evento.nome == "TJR 2026"))
    persistido = resultado.scalar_one()

    assert evento.id == persistido.id
    assert persistido.ano == 2026


async def test_seed_evento_e_idempotente(db_session):
    primeiro = await seed_evento(db_session)
    await db_session.flush()
    segundo = await seed_evento(db_session)
    await db_session.flush()

    resultado = await db_session.execute(select(Evento).where(Evento.nome == "TJR 2026"))
    eventos = resultado.scalars().all()

    assert len(eventos) == 1
    assert primeiro.id == segundo.id


async def test_seed_modalidades_cria_todas_as_modalidades_do_tjr(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await db_session.flush()

    assert len(modalidades) == len(MODALIDADES_TJR)
    nomes = {m.nome for m in modalidades}
    assert nomes == {spec["nome"] for spec in MODALIDADES_TJR}
    niveis_esperados_por_nome = {
        spec["nome"]: spec.get("niveis_aplicaveis", [1, 2, 3, 4]) for spec in MODALIDADES_TJR
    }
    for modalidade in modalidades:
        assert modalidade.evento_id == evento.id
        assert modalidade.status == ModalidadeStatus.PUBLICADA
        assert modalidade.niveis_aplicaveis == niveis_esperados_por_nome[modalidade.nome]


async def test_seed_modalidades_confronto_decide_formato_de_chaveamento_automaticamente(
    db_session,
):
    # formato_chaveamento=None em CONFRONTO agora significa "decida sozinho
    # por nivel" (gerar_chaveamento_confronto), nao "sem formato" -- o seed
    # de 2026 nao configura mais um valor fixo pra nenhuma modalidade de
    # combate.
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    por_nome = {m.nome: m for m in modalidades}
    assert por_nome["Sumô"].tipo_disputa == TipoDisputa.CONFRONTO
    assert por_nome["Sumô"].formato_chaveamento is None
    assert por_nome["Dança"].tipo_disputa == TipoDisputa.INDIVIDUAL
    assert por_nome["Dança"].formato_chaveamento is None


async def test_seed_modalidades_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    await seed_modalidades(db_session, evento)
    await db_session.flush()
    await seed_modalidades(db_session, evento)
    await db_session.flush()

    resultado = await db_session.execute(
        select(Modalidade).where(Modalidade.evento_id == evento.id)
    )
    modalidades = resultado.scalars().all()

    assert len(modalidades) == len(MODALIDADES_TJR)


async def test_seed_fichas_cria_ficha_publicada_para_cada_modalidade_de_ficha_unica(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    por_nome = {m.nome: m for m in modalidades}
    for nome in FICHAS_TJR:
        resultado = await db_session.execute(
            select(Ficha).where(Ficha.modalidade_id == por_nome[nome].id)
        )
        fichas_da_modalidade = resultado.scalars().all()
        assert len(fichas_da_modalidade) == 1
        assert fichas_da_modalidade[0].nivel is None
        assert fichas_da_modalidade[0].status == FichaStatus.PUBLICADA


async def test_seed_fichas_cria_uma_ficha_por_nivel_para_viagem_ao_centro_da_terra(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == viagem.id))
    fichas_por_nivel = {f.nivel: f for f in resultado.scalars().all()}

    assert set(fichas_por_nivel) == set(FICHA_VIAGEM_POR_NIVEL)
    for ficha in fichas_por_nivel.values():
        assert ficha.status == FichaStatus.PUBLICADA


async def test_seed_viagem_ao_centro_da_terra_tem_1_tentativa_por_rodada(db_session):
    # Os "1o cubo"/"2o cubo" da ficha oficial sao as duas metades de UMA
    # corrida so dentro da mesma rodada (ida, pega o 1o cubo, volta, entrega,
    # vai de novo, pega o 2o) - nao duas tentativas/lancamentos separados.
    # "Atravessar a borda" ja cobre o robo saindo da arena e reiniciando
    # dentro da mesma rodada; tentativa nao entra nesse quesito.
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")

    assert viagem.tentativas_por_rodada == 1


async def test_seed_fichas_viagem_tem_grupos_1o_e_2o_cubo_com_os_mesmos_criterios(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")
    resultado = await db_session.execute(
        select(Ficha).where(Ficha.modalidade_id == viagem.id, Ficha.nivel == 1)
    )
    ficha_nivel_1 = resultado.scalar_one()

    resultado_grupos = await db_session.execute(
        select(Grupo).where(Grupo.ficha_id == ficha_nivel_1.id).order_by(Grupo.ordem)
    )
    grupos = resultado_grupos.scalars().all()
    assert [g.nome for g in grupos] == ["1º Cubo", "2º Cubo"]

    criterios_esperados = {
        "Atingir vértice sem o alvo, na ida",
        "Atingir o centro do cubo sem o alvo, na ida",
        "Capturar o alvo A, no centro do cubo",
        "Atingir vértice com o alvo, na volta",
        "Atingir o início da arena com o alvo, na volta",
        "Soltar o alvo A, no início da arena",
        "Atravessar a borda",
    }
    for grupo in grupos:
        resultado_criterios = await db_session.execute(
            select(Criterio).where(Criterio.grupo_id == grupo.id)
        )
        nomes = {c.nome for c in resultado_criterios.scalars().all()}
        assert nomes == criterios_esperados


async def test_seed_fichas_viagem_nivel_3_e_4_tem_grupo_extra_de_reinicio(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")
    resultado = await db_session.execute(
        select(Ficha).where(Ficha.modalidade_id == viagem.id, Ficha.nivel == 3)
    )
    ficha_nivel_3 = resultado.scalar_one()

    resultado_grupos = await db_session.execute(
        select(Grupo).where(Grupo.ficha_id == ficha_nivel_3.id).order_by(Grupo.ordem)
    )
    grupos = resultado_grupos.scalars().all()
    nomes_grupos = [g.nome for g in grupos]
    assert nomes_grupos[:2] == ["1º Cubo", "2º Cubo"]

    grupo_extra = grupos[2]
    resultado_criterios = await db_session.execute(
        select(Criterio).where(Criterio.grupo_id == grupo_extra.id)
    )
    criterios = resultado_criterios.scalars().all()
    assert [c.nome for c in criterios] == ["Reinício entre as rodadas"]


async def test_seed_fichas_viagem_nivel_1_e_2_nao_tem_grupo_de_reinicio(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")
    resultado = await db_session.execute(
        select(Ficha).where(Ficha.modalidade_id == viagem.id, Ficha.nivel == 1)
    )
    ficha_nivel_1 = resultado.scalar_one()

    resultado_grupos = await db_session.execute(
        select(Grupo).where(Grupo.ficha_id == ficha_nivel_1.id)
    )
    grupos = resultado_grupos.scalars().all()
    assert len(grupos) == 2


async def test_seed_fichas_cria_grupos_e_criterios_da_especificacao(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    danca = next(m for m in modalidades if m.nome == "Dança")
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == danca.id))
    ficha = resultado.scalar_one()

    resultado_grupos = await db_session.execute(select(Grupo).where(Grupo.ficha_id == ficha.id))
    grupos = resultado_grupos.scalars().all()
    assert len(grupos) == len(FICHAS_TJR["Dança"])

    resultado_criterios = await db_session.execute(
        select(Criterio).where(Criterio.grupo_id.in_([g.id for g in grupos]))
    )
    criterios = resultado_criterios.scalars().all()
    total_esperado = sum(len(criterios_spec) for _, criterios_spec in FICHAS_TJR["Dança"])
    assert len(criterios) == total_esperado


async def test_seed_fichas_danca_penalidades_nao_tem_efeito_no_calculo(db_session):
    # Pedido do cliente (2026-08-25): tirar a retirada de pontos das
    # penalidades em geral (excecao: Corrida de Carros Autonomos, que
    # precisa da penalidade pra decidir quem vence o combate). Os dois
    # criterios da Danca sao MODIFICADOR, nao tem campo "pontos" simples --
    # "Paralisacao" virou PERCENTUAL 0% (era ZERA_TOTAL) e "Ultrapassou 5
    # minutos" ficou PERCENTUAL 0% (era 10%). Critérios continuam existindo
    # (o arbitro ainda registra a ocorrencia), so sem efeito no total.
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    criterios = await _criterios_da_modalidade(db_session, modalidades, "Dança")
    por_nome = {c.nome: c for c in criterios}

    paralisacao = por_nome["Paralisação durante o desempenho"]
    assert paralisacao.modificador_tipo == ModificadorTipo.PERCENTUAL
    assert float(paralisacao.modificador_valor) == 0.0

    ultrapassou = por_nome["Ultrapassou 5 minutos de apresentação"]
    assert ultrapassou.modificador_tipo == ModificadorTipo.PERCENTUAL
    assert float(ultrapassou.modificador_valor) == 0.0


async def test_seed_fichas_viagem_penalidades_nao_descontam_pontos(db_session):
    # Mesmo pedido acima, aplicado aos criterios CONTADOR/PENALIDADE
    # simples da Viagem ao Centro da Terra: mantem o criterio, zera pontos.
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    viagem = next(m for m in modalidades if m.nome == "Viagem ao Centro da Terra")

    resultado_nivel_1 = await db_session.execute(
        select(Ficha).where(Ficha.modalidade_id == viagem.id, Ficha.nivel == 1)
    )
    ficha_nivel_1 = resultado_nivel_1.scalar_one()
    resultado_grupos_1 = await db_session.execute(
        select(Grupo).where(Grupo.ficha_id == ficha_nivel_1.id)
    )
    grupos_1 = resultado_grupos_1.scalars().all()
    resultado_criterios_1 = await db_session.execute(
        select(Criterio).where(Criterio.grupo_id.in_([g.id for g in grupos_1]))
    )
    atravessar_borda = [
        c for c in resultado_criterios_1.scalars().all() if c.nome == "Atravessar a borda"
    ]
    assert len(atravessar_borda) == 2  # 1o Cubo e 2o Cubo
    assert all(float(c.pontos) == 0.0 for c in atravessar_borda)

    resultado_nivel_3 = await db_session.execute(
        select(Ficha).where(Ficha.modalidade_id == viagem.id, Ficha.nivel == 3)
    )
    ficha_nivel_3 = resultado_nivel_3.scalar_one()
    resultado_grupos_3 = await db_session.execute(
        select(Grupo).where(Grupo.ficha_id == ficha_nivel_3.id)
    )
    grupos_3 = resultado_grupos_3.scalars().all()
    resultado_criterios_3 = await db_session.execute(
        select(Criterio).where(Criterio.grupo_id.in_([g.id for g in grupos_3]))
    )
    reinicio = next(
        c for c in resultado_criterios_3.scalars().all() if c.nome == "Reinício entre as rodadas"
    )
    assert float(reinicio.pontos) == 0.0


async def test_seed_fichas_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)
    await db_session.flush()
    await seed_fichas(db_session, modalidades)
    await db_session.flush()

    sumo = next(m for m in modalidades if m.nome == "Sumô")
    resultado = await db_session.execute(select(Ficha).where(Ficha.modalidade_id == sumo.id))
    assert len(resultado.scalars().all()) == 1


async def test_seed_fichas_cabo_de_guerra_tem_criterio_escala_resultado_do_arrasto(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    criterio = await _criterio_unico_da_modalidade(db_session, modalidades, "Cabo de Guerra")

    assert criterio.nome == "Resultado do arrasto"
    assert criterio.tipo == CriterioTipo.ESCALA
    assert criterio.valores_permitidos == [0, 1, 2]


async def test_seed_fichas_sumo_tem_criterio_escala_resultado_do_combate(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    criterio = await _criterio_unico_da_modalidade(db_session, modalidades, "Sumô")

    assert criterio.nome == "Resultado do combate"
    assert criterio.tipo == CriterioTipo.ESCALA
    assert criterio.valores_permitidos == [0, 1, 2]


async def test_seed_fichas_corrida_de_carros_tem_os_criterios_da_ficha_oficial(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    criterios = await _criterios_da_modalidade(
        db_session, modalidades, "Corrida de Carros Autônomos"
    )
    por_nome = {c.nome: c for c in criterios}

    assert set(por_nome) == {
        "Evitar a colisão",
        "Colisão com a parte traseira do outro",
        "Evasão da pista",
        "Posicionamento transversal",
        "Percurso em sentido contrário",
        "Carro que ficou na frente",
    }

    evitar_colisao = por_nome["Evitar a colisão"]
    assert evitar_colisao.tipo == CriterioTipo.CONTADOR
    assert evitar_colisao.categoria == CategoriaCriterio.PONTUACAO
    assert float(evitar_colisao.pontos) == 1.0

    for nome_violacao in (
        "Colisão com a parte traseira do outro",
        "Evasão da pista",
        "Posicionamento transversal",
        "Percurso em sentido contrário",
    ):
        violacao = por_nome[nome_violacao]
        assert violacao.tipo == CriterioTipo.BOOLEANO
        assert violacao.categoria == CategoriaCriterio.PENALIDADE

    ficou_na_frente = por_nome["Carro que ficou na frente"]
    assert ficou_na_frente.tipo == CriterioTipo.BOOLEANO
    assert ficou_na_frente.categoria == CategoriaCriterio.PONTUACAO
    assert float(ficou_na_frente.pontos) > sum(
        float(por_nome[n].pontos)
        for n in (
            "Colisão com a parte traseira do outro",
            "Evasão da pista",
            "Posicionamento transversal",
            "Percurso em sentido contrário",
        )
    )


async def test_carro_que_violou_perde_a_corrida_mesmo_com_evitar_colisao_marcado(db_session):
    """O carro que colide/evade/etc perde a corrida na comparacao de totais,
    mesmo acumulando pontos em 'Evitar a colisao' - a violacao tem que
    dominar o total, e nao so descontar um pouco.
    """
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    criterios = await _criterios_da_modalidade(
        db_session, modalidades, "Corrida de Carros Autônomos"
    )
    por_nome = {c.nome: c for c in criterios}

    pontos_violador = float(por_nome["Evitar a colisão"].pontos) * 5 - float(
        por_nome["Evasão da pista"].pontos
    )
    pontos_vencedor = float(por_nome["Carro que ficou na frente"].pontos)

    assert max(pontos_violador, 0) < pontos_vencedor


async def test_seed_modalidades_corrida_de_carros_roda_melhor_de_3(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    corrida = next(m for m in modalidades if m.nome == "Corrida de Carros Autônomos")

    assert corrida.tentativas_por_rodada == 3


async def test_seed_equipes_credenciadas_cria_quatro_por_nivel(db_session):
    equipes = await seed_equipes_credenciadas(db_session)

    assert len(equipes) == len(EQUIPES_TJR)
    for nivel in (1, 2, 3, 4):
        do_nivel = [e for e in equipes if e.nivel == nivel]
        assert len(do_nivel) == 4


async def test_seed_equipes_credenciadas_e_idempotente(db_session):
    await seed_equipes_credenciadas(db_session)
    await db_session.flush()
    await seed_equipes_credenciadas(db_session)
    await db_session.flush()

    resultado = await db_session.execute(select(Equipe).where(Equipe.nome.like("Nível%")))
    assert len(resultado.scalars().all()) == len(EQUIPES_TJR)


def _inscricoes_esperadas(modalidades, equipes) -> int:
    return sum(
        1
        for modalidade in modalidades
        for equipe in equipes
        if equipe.nivel in modalidade.niveis_aplicaveis
    )


async def test_seed_inscricoes_credencia_toda_equipe_em_toda_modalidade_do_seu_nivel(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)

    inscricoes = await seed_inscricoes(db_session, modalidades, equipes)

    assert len(inscricoes) == _inscricoes_esperadas(modalidades, equipes)


async def test_seed_inscricoes_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)

    await seed_inscricoes(db_session, modalidades, equipes)
    await db_session.flush()
    await seed_inscricoes(db_session, modalidades, equipes)
    await db_session.flush()

    resultado = await db_session.execute(select(Inscricao))
    assert len(resultado.scalars().all()) == _inscricoes_esperadas(modalidades, equipes)


async def test_seed_modalidades_individual_tem_duracao_e_pausa_configuradas(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    individuais = [m for m in modalidades if m.tipo_disputa == TipoDisputa.INDIVIDUAL]
    assert len(individuais) > 0
    for modalidade in individuais:
        assert modalidade.duracao_maxima_rodada_seg is not None
        assert modalidade.duracao_maxima_rodada_seg > 0
        assert modalidade.pausa_entre_rodadas_seg is not None


_MODALIDADES_ARENA_POR_NIVEL = {"Resgate no Plano", "Resgate de Alto Risco"}


def _qtd_arenas_esperada_no_seed(modalidade: Modalidade) -> int:
    # Resgate no Plano/Alto Risco tem arena dedicada por nivel (2, 3 e 4);
    # as demais modalidades INDIVIDUAL continuam com 1 arena generica
    # (niveis_aplicaveis=None, aberta pra qualquer nivel).
    return 3 if modalidade.nome in _MODALIDADES_ARENA_POR_NIVEL else 1


async def test_seed_arenas_cria_arena_ativa_para_cada_modalidade_individual(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    coordenador = await seed_coordenador(db_session, email="arenas-1@tjr.app", senha="senha-123")

    arenas = await seed_arenas(db_session, modalidades, usuario_id=coordenador.id)

    individuais = [m for m in modalidades if m.tipo_disputa == TipoDisputa.INDIVIDUAL]
    assert len(arenas) == sum(_qtd_arenas_esperada_no_seed(m) for m in individuais)
    for arena in arenas:
        assert arena.ativo is True


async def test_seed_arenas_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    coordenador = await seed_coordenador(db_session, email="arenas-2@tjr.app", senha="senha-123")

    await seed_arenas(db_session, modalidades, usuario_id=coordenador.id)
    await db_session.flush()
    await seed_arenas(db_session, modalidades, usuario_id=coordenador.id)
    await db_session.flush()

    individuais = [m for m in modalidades if m.tipo_disputa == TipoDisputa.INDIVIDUAL]
    resultado = await db_session.execute(select(Arena))
    assert len(resultado.scalars().all()) == sum(
        _qtd_arenas_esperada_no_seed(m) for m in individuais
    )


async def test_seed_arenas_resgate_no_plano_e_alto_risco_tem_uma_arena_por_nivel(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    coordenador = await seed_coordenador(db_session, email="arenas-3@tjr.app", senha="senha-123")

    arenas = await seed_arenas(db_session, modalidades, usuario_id=coordenador.id)

    por_nome = {m.nome: m for m in modalidades}
    for nome in _MODALIDADES_ARENA_POR_NIVEL:
        arenas_da_modalidade = [a for a in arenas if a.modalidade_id == por_nome[nome].id]
        niveis = sorted(a.niveis_aplicaveis[0] for a in arenas_da_modalidade)
        assert niveis == [2, 3, 4]

    danca = por_nome["Dança"]
    arenas_danca = [a for a in arenas if a.modalidade_id == danca.id]
    assert len(arenas_danca) == 1
    assert arenas_danca[0].niveis_aplicaveis is None


def _qtd_rodadas_esperada_no_seed(modalidade: Modalidade) -> int:
    # MATA_MATA so pode ter a Rodada 1 pre-gerada: as proximas dependem de
    # quem vence cada partida (avancar_se_rodada_completa gera dinamicamente
    # conforme o chaveamento avanca) - nao da pra saber os confrontos de
    # antemao. TODOS_CONTRA_TODOS (explicito ou decidido automaticamente,
    # ver gerar_chaveamento_confronto) gera exatamente o que o metodo do
    # circulo precisa pras equipes daquele nivel, nao mais o teto de
    # `qtd_rodadas` (o seed credencia 4 equipes por nivel em toda modalidade
    # de confronto, sempre <=5 -> sempre vira todos-contra-todos hoje).
    if modalidade.nome == "Sumô RC 1,5 kg":
        # Sumo RC e Sumo tradicional nao podem ficar abertos ao mesmo tempo
        # (mesmo robo fisico possivel) - Sumo vem antes na ordem do seed e
        # fica com combate pendente, entao Sumo RC e pulado (seed_rodadas
        # engole o 422 MODALIDADE_CONFLITANTE_EM_ANDAMENTO de proposito).
        return 0
    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        if modalidade.formato_chaveamento == FormatoChaveamento.MATA_MATA:
            return 1
        return _rodadas_necessarias(4)
    return modalidade.qtd_rodadas


async def test_seed_rodadas_cria_qtd_rodadas_para_cada_modalidade(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)
    await seed_inscricoes(db_session, modalidades, equipes)
    coordenador = await seed_coordenador(db_session, email="rodadas-1@tjr.app", senha="senha-123")

    rodadas = await seed_rodadas(db_session, modalidades, usuario_id=coordenador.id)

    assert len(rodadas) == sum(_qtd_rodadas_esperada_no_seed(m) for m in modalidades)


async def test_seed_rodadas_confronto_ja_vem_com_partidas(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)
    await seed_inscricoes(db_session, modalidades, equipes)
    coordenador = await seed_coordenador(db_session, email="rodadas-2@tjr.app", senha="senha-123")

    await seed_rodadas(db_session, modalidades, usuario_id=coordenador.id)

    sumo = next(m for m in modalidades if m.nome == "Sumô")
    resultado = await db_session.execute(select(Rodada).where(Rodada.modalidade_id == sumo.id))
    primeira_rodada = next(r for r in resultado.scalars().all() if r.numero == 1)
    resultado_partidas = await db_session.execute(
        select(Partida).where(Partida.rodada_id == primeira_rodada.id)
    )
    assert len(resultado_partidas.scalars().all()) > 0


async def test_seed_rodadas_mata_mata_nao_pre_gera_rodadas_futuras(db_session):
    # Bug real (historico): seed_rodadas chamava o pareamento generico
    # (round-robin, "metodo do circulo") pra toda modalidade de CONFRONTO,
    # inclusive quando o formato era MATA_MATA - isso pre-criava rodadas
    # futuras com confrontos que nao dependiam de quem venceria a rodada
    # anterior (errado pro bracket) e deixava `gerar_chaveamento_confronto`
    # inacessivel depois (409 CHAVEAMENTO_JA_INICIADO, ja que ja existia
    # rodada). O seed real de 2026 nao seta mais formato_chaveamento
    # explicito (vira decisao automatica por nivel - com 4 equipes
    # credenciadas por nivel, sempre da <=5 e vira todos-contra-todos, ver
    # test_seed_rodadas_cria_qtd_rodadas_para_cada_modalidade), mas o escape
    # manual (coordenador forca MATA_MATA numa modalidade) ainda precisa
    # desse comportamento certo - so a Rodada 1 pronta no seed; as seguintes
    # vem de `avancar_se_rodada_completa`, so depois que as partidas da
    # rodada atual fecharem de verdade.
    evento = await seed_evento(db_session)
    coordenador = await seed_coordenador(
        db_session, email="rodadas-mata-mata@tjr.app", senha="senha-123"
    )
    modalidade_forcada = Modalidade(
        evento_id=evento.id,
        nome="Combate Forcado Mata-Mata",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        niveis_aplicaveis=[1, 2, 3, 4],
        ficha_unica_entre_niveis=True,
        qtd_rodadas=5,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.SOMA_RODADAS,
        status=ModalidadeStatus.PUBLICADA,
    )
    db_session.add(modalidade_forcada)
    await db_session.flush()
    equipes = await seed_equipes_credenciadas(db_session)
    await seed_inscricoes(db_session, [modalidade_forcada], equipes)

    await seed_rodadas(db_session, [modalidade_forcada], usuario_id=coordenador.id)

    resultado = await db_session.execute(
        select(Rodada).where(Rodada.modalidade_id == modalidade_forcada.id)
    )
    numeros = sorted(r.numero for r in resultado.scalars().all())
    assert numeros == [1]


async def test_seed_rodadas_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)
    await seed_inscricoes(db_session, modalidades, equipes)
    coordenador = await seed_coordenador(db_session, email="rodadas-3@tjr.app", senha="senha-123")

    await seed_rodadas(db_session, modalidades, usuario_id=coordenador.id)
    await db_session.flush()
    await seed_rodadas(db_session, modalidades, usuario_id=coordenador.id)
    await db_session.flush()

    resultado = await db_session.execute(select(Rodada))
    assert len(resultado.scalars().all()) == sum(
        _qtd_rodadas_esperada_no_seed(m) for m in modalidades
    )


async def test_seed_agendamentos_cobre_toda_equipe_inscrita_em_modalidade_individual(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)
    await seed_inscricoes(db_session, modalidades, equipes)
    coordenador = await seed_coordenador(db_session, email="agend-1@tjr.app", senha="senha-123")
    await seed_arenas(db_session, modalidades, usuario_id=coordenador.id)
    await seed_rodadas(db_session, modalidades, usuario_id=coordenador.id)

    agendamentos = await seed_agendamentos(
        db_session, evento, modalidades, usuario_id=coordenador.id
    )

    danca = next(m for m in modalidades if m.nome == "Dança")
    resultado_rodadas = await db_session.execute(
        select(Rodada).where(Rodada.modalidade_id == danca.id)
    )
    rodada_ids = {r.id for r in resultado_rodadas.scalars().all()}
    da_danca = [a for a in agendamentos if a.rodada_id in rodada_ids]

    equipes_do_nivel = [e for e in equipes if e.nivel in danca.niveis_aplicaveis]
    assert len(da_danca) == len(equipes_do_nivel) * danca.qtd_rodadas


async def test_seed_agendamentos_e_idempotente(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    equipes = await seed_equipes_credenciadas(db_session)
    await seed_inscricoes(db_session, modalidades, equipes)
    coordenador = await seed_coordenador(db_session, email="agend-2@tjr.app", senha="senha-123")
    await seed_arenas(db_session, modalidades, usuario_id=coordenador.id)
    await seed_rodadas(db_session, modalidades, usuario_id=coordenador.id)

    await seed_agendamentos(db_session, evento, modalidades, usuario_id=coordenador.id)
    await db_session.flush()
    total_antes = (await db_session.execute(select(Agendamento))).scalars().all()

    await seed_agendamentos(db_session, evento, modalidades, usuario_id=coordenador.id)
    await db_session.flush()
    total_depois = (await db_session.execute(select(Agendamento))).scalars().all()

    assert len(total_antes) == len(total_depois)


async def test_seed_modalidades_cabo_de_guerra_e_sumo_usam_soma_pontos(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    por_nome = {m.nome: m for m in modalidades}
    assert por_nome["Cabo de Guerra"].decisao_partida == DecisaoPartida.SOMA_PONTOS
    assert por_nome["Sumô"].decisao_partida == DecisaoPartida.SOMA_PONTOS


async def test_seed_modalidades_sumo_rc_e_sumo_3kg_tem_as_mesmas_regras_do_sumo(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    por_nome = {m.nome: m for m in modalidades}
    sumo = por_nome["Sumô"]

    for nome in ("Sumô RC 1,5 kg", "Sumô 3 kg"):
        outro = por_nome[nome]
        assert outro.tipo_disputa == sumo.tipo_disputa == TipoDisputa.CONFRONTO
        assert outro.formato_chaveamento == sumo.formato_chaveamento is None
        assert outro.tentativas_por_rodada == sumo.tentativas_por_rodada == 2
        assert outro.decisao_partida == sumo.decisao_partida == DecisaoPartida.SOMA_PONTOS


async def test_seed_modalidades_sumo_rc_e_sumo_3kg_sao_so_nivel_absoluto(db_session):
    # Nivel 1 e reaproveitado como "ABSOLUTO" (rotulo so no front) -- essas
    # 2 modalidades so tem equipe nivel 0/ABSOLUTO na planilha real, entao
    # niveis_aplicaveis fica restrito a [1] em vez do [1,2,3,4] padrao.
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    por_nome = {m.nome: m for m in modalidades}
    assert por_nome["Sumô RC 1,5 kg"].niveis_aplicaveis == [1]
    assert por_nome["Sumô 3 kg"].niveis_aplicaveis == [1]
    assert por_nome["Sumô"].niveis_aplicaveis == [1, 2, 3, 4]


async def test_seed_fichas_sumo_rc_e_sumo_3kg_tem_criterio_escala_resultado_do_combate(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)
    await seed_fichas(db_session, modalidades)

    for nome in ("Sumô RC 1,5 kg", "Sumô 3 kg"):
        criterio = await _criterio_unico_da_modalidade(db_session, modalidades, nome)
        assert criterio.nome == "Resultado do combate"
        assert criterio.tipo == CriterioTipo.ESCALA
        assert criterio.valores_permitidos == [0, 1, 2]


async def test_seed_modalidades_corrida_de_carros_usa_combates_vencidos(db_session):
    evento = await seed_evento(db_session)
    modalidades = await seed_modalidades(db_session, evento)

    corrida = next(m for m in modalidades if m.nome == "Corrida de Carros Autônomos")
    assert corrida.decisao_partida == DecisaoPartida.COMBATES_VENCIDOS
