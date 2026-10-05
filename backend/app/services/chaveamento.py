import json
from uuid import UUID

from sqlalchemy import delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.chave import Chave, ChaveEquipe
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import DecisaoPartida, FormatoChaveamento, Modalidade, TipoDisputa
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.services.audit import registrar_audit_log
from app.services.equipe import obter_equipe
from app.services.modalidade import obter_modalidade


def _dump(obj) -> dict:
    bruto = {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}
    return json.loads(json.dumps(bruto, default=str))


async def _obter_ou_criar_rodada(db: AsyncSession, modalidade_id: UUID, numero: int) -> Rodada:
    rodada = await db.scalar(
        select(Rodada).where(Rodada.modalidade_id == modalidade_id, Rodada.numero == numero)
    )
    if rodada is None:
        rodada = Rodada(
            modalidade_id=modalidade_id,
            numero=numero,
            modo_horario=ModoHorario.AUTOMATICO,
            status=RodadaStatus.AGENDADA,
        )
        db.add(rodada)
        await db.flush()
    return rodada


async def _chave_em_comum(
    db: AsyncSession, modalidade_id: UUID, equipe_a_id: UUID, equipe_b_id: UUID
) -> UUID | None:
    chaves_por_equipe: dict[UUID, UUID] = dict(
        (
            await db.execute(
                select(ChaveEquipe.equipe_id, ChaveEquipe.chave_id)
                .join(Chave, ChaveEquipe.chave_id == Chave.id)
                .where(
                    Chave.modalidade_id == modalidade_id,
                    ChaveEquipe.equipe_id.in_([equipe_a_id, equipe_b_id]),
                )
            )
        ).all()
    )
    chave_a = chaves_por_equipe.get(equipe_a_id)
    return (
        chave_a if chave_a is not None and chave_a == chaves_por_equipe.get(equipe_b_id) else None
    )


async def criar_partida_manual(
    db: AsyncSession,
    modalidade_id: UUID,
    equipe_a_id: UUID,
    equipe_b_id: UUID | None,
    *,
    rodada_numero: int,
    formato: FormatoChaveamento,
    usuario_id: UUID,
) -> Partida:
    """Unico jeito de criar partida de combate: o coordenador monta cada
    confronto na mao (chaveamento feito fora do sistema), escolhendo a rodada
    e o tipo. O sistema nunca gera nem avanca chaveamento sozinho.

    - `formato` TODOS_CONTRA_TODOS = "fase de grupos": aceita empate (partida
      fecha EMPATADA), nao aceita bye. Se as duas equipes estao na mesma
      `Chave` da modalidade, a partida herda essa chave (selo visual +
      classificacao por chave).
    - `formato` MATA_MATA = "eliminatoria": nao aceita empate (libera o
      combate extra de desempate), aceita bye (equipe_b_id=None fecha a
      partida sozinha, equipe A avanca). Nunca carrega chave.

    Rodada `rodada_numero` e reaproveitada se ja existir, ou criada. Uma
    equipe so pode ter uma partida por rodada; em rodadas diferentes, pode
    quantas precisar (fase de grupos, semifinal, final...).
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="MODALIDADE_NAO_E_CONFRONTO",
            mensagem="Chaveamento so pode ser montado para modalidade de confronto.",
            status_code=422,
        )

    if equipe_b_id is not None and equipe_a_id == equipe_b_id:
        raise AppError(
            codigo="EQUIPES_IGUAIS",
            mensagem="As duas equipes de uma partida precisam ser diferentes.",
            status_code=422,
        )

    if equipe_b_id is None and formato != FormatoChaveamento.MATA_MATA:
        raise AppError(
            codigo="BYE_SO_EM_ELIMINATORIA",
            mensagem="Bye (sem adversario) so existe em confronto eliminatorio.",
            status_code=422,
        )

    equipe_a = await obter_equipe(db, equipe_a_id)
    equipe_b = await obter_equipe(db, equipe_b_id) if equipe_b_id is not None else None

    if equipe_b is not None and equipe_b.nivel != equipe_a.nivel:
        raise AppError(
            codigo="NIVEIS_INCOMPATIVEIS",
            mensagem="As duas equipes de uma partida precisam ser do mesmo nivel.",
            status_code=422,
        )

    for equipe in filter(None, [equipe_a, equipe_b]):
        if not equipe.presente:
            raise AppError(
                codigo="EQUIPE_AUSENTE",
                mensagem=f"A equipe '{equipe.nome}' esta marcada como ausente.",
                status_code=422,
            )
        inscrita = await db.scalar(
            select(Inscricao).where(
                Inscricao.equipe_id == equipe.id, Inscricao.modalidade_id == modalidade_id
            )
        )
        if inscrita is None:
            raise AppError(
                codigo="EQUIPE_NAO_INSCRITA",
                mensagem=f"A equipe '{equipe.nome}' nao esta inscrita nesta modalidade.",
                status_code=422,
            )

    rodada = await _obter_ou_criar_rodada(db, modalidade_id, rodada_numero)

    ids_envolvidos = [e.id for e in filter(None, [equipe_a, equipe_b])]
    ja_tem_partida = await db.scalar(
        select(Partida.id)
        .where(
            Partida.rodada_id == rodada.id,
            (Partida.equipe_a_id.in_(ids_envolvidos) | Partida.equipe_b_id.in_(ids_envolvidos)),
        )
        .limit(1)
    )
    if ja_tem_partida is not None:
        raise AppError(
            codigo="EQUIPE_JA_TEM_PARTIDA",
            mensagem="Uma dessas equipes ja tem partida nesta rodada.",
            status_code=409,
        )

    chave_id = None
    if formato == FormatoChaveamento.TODOS_CONTRA_TODOS:
        chave_id = await _chave_em_comum(db, modalidade_id, equipe_a.id, equipe_b.id)

    partida = Partida(
        rodada_id=rodada.id,
        equipe_a_id=equipe_a.id,
        equipe_b_id=equipe_b_id,
        nivel=equipe_a.nivel,
        chave_id=chave_id,
        formato_chaveamento=formato,
        vencedor_id=equipe_a.id if equipe_b_id is None else None,
        status=PartidaStatus.ENCERRADA if equipe_b_id is None else PartidaStatus.AGENDADA,
    )
    db.add(partida)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="partida",
        entidade_id=partida.id,
        acao="CRIAR_PARTIDA_MANUAL",
        antes=None,
        depois=_dump(partida),
    )

    return partida


async def registrar_resultado_lancamento(
    db: AsyncSession, lancamento: Lancamento, *, usuario_id: UUID
) -> None:
    """Chamado depois que um lancamento e confirmado (ou corrigido). Se ele
    pertence a uma partida de confronto e os dois lados ja confirmaram todos
    os combates da partida (`modalidade.tentativas_por_rodada`, um lancamento
    por tentativa por equipe - default 1, mas em modalidade de combate e 3:
    "melhor de 3"), decide o vencedor da partida:

    - Cada tentativa e um combate: quem tem o maior total naquela tentativa
      vence o combate; combate empatado nao conta ponto pra ninguem.
    - Vencedor da partida = quem venceu mais combates. Contagem de combates
      empatada (incluindo 0x0): mata-mata deixa a partida aberta (sem
      resolucao automatica, precisa de correcao/relancamento ou combate
      extra de desempate); todos-contra-todos fecha como EMPATADA.
    - Nunca gera a proxima rodada: o chaveamento e montado na mao pelo
      coordenador (criar_partida_manual), inclusive semifinal/final.

    Nao faz nada fora de confronto, em formato sem essas regras, ou enquanto
    algum dos dois lados nao tiver confirmado todos os combates da partida.
    """
    if lancamento.partida_id is None:
        return

    partida = await db.get(Partida, lancamento.partida_id)
    if partida is None:
        return
    if partida.equipe_b_id is None:
        return

    rodada = await db.get(Rodada, partida.rodada_id)
    modalidade = await db.get(Modalidade, rodada.modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        return

    eh_chaveamento = partida.formato_chaveamento == FormatoChaveamento.MATA_MATA
    eh_todos_contra_todos = partida.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS

    resultado = await db.execute(
        select(Lancamento).where(
            Lancamento.partida_id == partida.id,
            Lancamento.status == LancamentoStatus.CONFIRMADO,
        )
    )
    por_equipe_tentativa = {
        (lanc.equipe_id, lanc.tentativa): lanc for lanc in resultado.scalars().all()
    }

    tentativas = range(1, modalidade.tentativas_por_rodada + 1)
    equipe_a_id, equipe_b_id = partida.equipe_a_id, partida.equipe_b_id
    if not all((equipe_a_id, t) in por_equipe_tentativa for t in tentativas):
        return
    if not all((equipe_b_id, t) in por_equipe_tentativa for t in tentativas):
        return

    # Duas formas de decidir a partida a partir dos combates confirmados
    # (Modalidade.decisao_partida, default COMBATES_VENCIDOS):
    # - COMBATES_VENCIDOS (regra historica): conta quantos combates
    #   individuais cada equipe ganhou (quem tem mais pontos NAQUELE
    #   combate), e quem ganha mais combates vence a partida - igual a um
    #   melhor-de-3 de sets, nao soma pontos entre combates.
    # - SOMA_PONTOS: soma o total de todos os combates e quem tiver mais
    #   pontos no total vence - pensado pra Cabo de Guerra/Sumo, onde cada
    #   round vale um numero de pontos diferente (ex.: Fosso=2, Arraste
    #   Parcial=1) e isso precisa se acumular, nao so contar quem venceu
    #   mais rounds.
    usa_soma = modalidade.decisao_partida == DecisaoPartida.SOMA_PONTOS

    vitorias_a = vitorias_b = 0
    soma_a = soma_b = 0.0
    for t in tentativas:
        total_a = float(por_equipe_tentativa[(equipe_a_id, t)].total)
        total_b = float(por_equipe_tentativa[(equipe_b_id, t)].total)
        soma_a += total_a
        soma_b += total_b
        if total_a > total_b:
            vitorias_a += 1
        elif total_b > total_a:
            vitorias_b += 1

    pontuacao_a = soma_a if usa_soma else vitorias_a
    pontuacao_b = soma_b if usa_soma else vitorias_b

    if pontuacao_a == pontuacao_b and eh_chaveamento:
        # Ponto de ouro: se a decisao empatar, um combate extra na tentativa
        # seguinte (fora de tentativas_por_rodada) decide a partida, sem
        # reescrever o resultado dos combates anteriores - so se aplica a
        # mata-mata, onde a partida travada bloqueia o avanco do chaveamento
        # (todos-contra-todos aceita EMPATADA numa boa).
        tentativa_desempate = modalidade.tentativas_por_rodada + 1
        lanc_a_desempate = por_equipe_tentativa.get((equipe_a_id, tentativa_desempate))
        lanc_b_desempate = por_equipe_tentativa.get((equipe_b_id, tentativa_desempate))
        if lanc_a_desempate and lanc_b_desempate:
            total_a_desempate = float(lanc_a_desempate.total)
            total_b_desempate = float(lanc_b_desempate.total)
            if usa_soma:
                pontuacao_a += total_a_desempate
                pontuacao_b += total_b_desempate
            elif total_a_desempate > total_b_desempate:
                pontuacao_a += 1
            elif total_b_desempate > total_a_desempate:
                pontuacao_b += 1

    # Recalcula sempre, inclusive com a partida ja decidida: uma correcao de
    # lancamento (coordenador) pode trocar o vencedor, virar empate (fase de
    # grupos -> EMPATADA) ou reabrir uma eliminatoria (empate -> espera o
    # combate extra de desempate). So grava/audita quando o estado muda.
    if pontuacao_a == pontuacao_b:
        novo_status = PartidaStatus.EMPATADA if eh_todos_contra_todos else PartidaStatus.AGENDADA
        vencedor_id = None
    else:
        novo_status = PartidaStatus.ENCERRADA
        vencedor_id = equipe_a_id if pontuacao_a > pontuacao_b else equipe_b_id

    if partida.status == novo_status and partida.vencedor_id == vencedor_id:
        return

    antes = {"status": partida.status.value, "vencedor_id": partida.vencedor_id}
    partida.status = novo_status
    partida.vencedor_id = vencedor_id
    await db.flush()

    acao = {
        PartidaStatus.ENCERRADA: "ENCERRAR",
        PartidaStatus.EMPATADA: "EMPATAR",
        PartidaStatus.AGENDADA: "REABRIR",
    }[novo_status]
    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="partida",
        entidade_id=partida.id,
        acao=acao,
        antes=json.loads(json.dumps(antes, default=str)),
        depois={
            "status": novo_status.value,
            "vencedor_id": str(vencedor_id) if vencedor_id else None,
            "pontuacao_a": pontuacao_a,
            "pontuacao_b": pontuacao_b,
        },
    )


async def resetar_chaveamento(
    db: AsyncSession, modalidade_id: UUID, *, usuario_id: UUID, justificativa: str
) -> None:
    """Apaga de verdade rodadas/partidas/lancamentos/itens de uma modalidade de
    confronto e recomeca o chaveamento do zero.

    Excecao deliberada a regra de "nunca apagar dado de pontuacao": serve pro
    caso em que o coordenador configurou o formato errado (ex.: mata-mata
    quando devia ser todos-contra-todos) e precisa desfazer tudo, nao so
    corrigir. Antes de apagar, grava um snapshot completo no audit_log
    (JSONB aceita qualquer coisa serializavel) - o rastro sobrevive mesmo sem
    as linhas originais. So depois disso a modalidade libera trocar
    formato_chaveamento (ver atualizar_modalidade) e gerar chaveamento de novo.
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="RESET_APENAS_CONFRONTO",
            mensagem="Reset de chaveamento so se aplica a modalidade de confronto.",
            status_code=422,
        )

    rodadas = list(
        (await db.execute(select(Rodada).where(Rodada.modalidade_id == modalidade_id)))
        .scalars()
        .all()
    )
    if not rodadas:
        return

    rodada_ids = [r.id for r in rodadas]
    partidas = list(
        (await db.execute(select(Partida).where(Partida.rodada_id.in_(rodada_ids)))).scalars().all()
    )
    lancamentos = list(
        (await db.execute(select(Lancamento).where(Lancamento.rodada_id.in_(rodada_ids))))
        .scalars()
        .all()
    )
    lancamento_ids = [lanc.id for lanc in lancamentos]
    itens = list(
        (
            await db.execute(
                select(LancamentoItem).where(LancamentoItem.lancamento_id.in_(lancamento_ids))
            )
        )
        .scalars()
        .all()
    )
    chaves = list(
        (await db.execute(select(Chave).where(Chave.modalidade_id == modalidade_id)))
        .scalars()
        .all()
    )
    chave_ids = [c.id for c in chaves]
    chave_equipes = (
        list(
            (await db.execute(select(ChaveEquipe).where(ChaveEquipe.chave_id.in_(chave_ids))))
            .scalars()
            .all()
        )
        if chave_ids
        else []
    )

    snapshot = {
        "rodadas": [_dump(r) for r in rodadas],
        "partidas": [_dump(p) for p in partidas],
        "lancamentos": [_dump(lanc) for lanc in lancamentos],
        "itens": [_dump(item) for item in itens],
        "chaves": [_dump(c) for c in chaves],
        "chave_equipes": [_dump(ce) for ce in chave_equipes],
    }

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade_id,
        acao="RESET_CHAVEAMENTO",
        antes=snapshot,
        depois=None,
        justificativa=justificativa,
    )

    await db.execute(delete(LancamentoItem).where(LancamentoItem.lancamento_id.in_(lancamento_ids)))
    await db.execute(delete(Lancamento).where(Lancamento.rodada_id.in_(rodada_ids)))
    await db.execute(delete(Partida).where(Partida.rodada_id.in_(rodada_ids)))
    if chave_ids:
        await db.execute(delete(ChaveEquipe).where(ChaveEquipe.chave_id.in_(chave_ids)))
        await db.execute(delete(Chave).where(Chave.id.in_(chave_ids)))
    await db.execute(delete(Rodada).where(Rodada.modalidade_id == modalidade_id))
    await db.flush()
