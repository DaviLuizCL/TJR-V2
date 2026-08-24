"""
Script avulso -- nao faz parte do app. Pontua as equipes ja criadas por
recriar_equipes.py em todas as 7 modalidades do evento real, garantindo que
times especificos (nome exato) terminem em 1o lugar em 24 combinacoes
modalidade+nivel pedidas pelo usuario. Sumo (mata-mata) fica totalmente
aleatorio, sem alvo.

So ADICIONA dado (rodada/agendamento/partida/lancamento) em cima do que ja
existe -- nunca apaga nada. Idempotente na parte de criar equipe/inscricao
(reaproveita se ja existir); a parte de pontuar NAO e idempotente (gera
lancamento novo a cada rodada rodada), entao so deve ser executado uma vez
contra um estado sem lancamento pre-existente nessas modalidades.

Uso:
    docker compose exec -T api python3 -m scripts.dados_teste.pontuar_simulacao
"""

import asyncio
import random
import uuid as uuidlib
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo
from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.ficha import Ficha
from app.models.inscricao import Inscricao
from app.models.modalidade import FormatoChaveamento, Modalidade, TipoDisputa
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import Rodada
from app.models.usuario import Usuario
from app.schemas.equipe import EquipeCreate
from app.schemas.inscricao import InscricaoCreate
from app.schemas.lancamento import ItemLancamentoInput, LancamentoCreate
from app.services import agendamento as agendamento_service
from app.services import chaveamento as chaveamento_service
from app.services import consolidacao as consolidacao_service
from app.services import ficha as ficha_service
from app.services import lancamento as lancamento_service
from app.services import rodada as rodada_service
from app.services.equipe import criar_equipe
from app.services.inscricao import criar_inscricao
from scripts.dados_teste.recriar_equipes import NOMES_ANEIS, NOMES_POTTER, SIGLAS_MODALIDADE

RNG = random.Random(42)

NOME_MODALIDADE_POR_SIGLA = {sigla: nome for nome, sigla in SIGLAS_MODALIDADE.items()}

# modalidade -> nivel -> nome do time que precisa vencer (base, sem franquia/sigla)
ALVOS: dict[str, dict[int, str]] = {
    "VCT": {1: "Slughorn", 2: "Eowyn", 3: "Bilbo", 4: "Theoden"},
    "RAR": {1: "Dobby", 2: "Hedwig", 3: "Hippogriff", 4: "Ithilien"},
    "RNP": {1: "Edoras", 2: "Celeborn", 3: "Frodo", 4: "Denethor"},
    "DAN": {1: "Gandalf", 2: "Azkaban", 3: "Fred", 4: "Fawkes"},
    "CCA": {1: "Bilbo", 2: "Faramir", 3: "Elendil", 4: "Flitwick"},
    "CDG": {1: "Dumbledore", 2: "Draco", 3: "Fluffy", 4: "Crookshanks"},
}

TETO_CONTADOR_SEM_LIMITE = 5


def _franquia(nome: str) -> str:
    return "POTTER" if nome in NOMES_POTTER else "ANEIS"


def _nome_completo(nome: str, nivel: int, sigla: str) -> str:
    return f"{nome} - {_franquia(nome)} - NV{nivel} - {sigla}"


# ---------------------------------------------------------------- equipes --


async def garantir_equipe_e_inscricao(
    db: AsyncSession, *, nome: str, nivel: int, modalidade_id, ator_id
) -> Equipe:
    equipe = await db.scalar(select(Equipe).where(Equipe.nome == nome))
    if equipe is None:
        equipe = await criar_equipe(
            db, EquipeCreate(nome=nome, nivel=nivel, ativo=True), usuario_id=ator_id
        )
        print(f"  [criada] {nome}")

    inscricao = await db.scalar(
        select(Inscricao).where(
            Inscricao.equipe_id == equipe.id, Inscricao.modalidade_id == modalidade_id
        )
    )
    if inscricao is None:
        await criar_inscricao(
            db,
            InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade_id),
            usuario_id=ator_id,
        )
    return equipe


# ---------------------------------------------------------------- rodadas --


async def preparar_rodadas(db: AsyncSession, modalidade: Modalidade, *, ator_id) -> list[Rodada]:
    existentes = list(
        (
            await db.execute(select(Rodada).where(Rodada.modalidade_id == modalidade.id))
        )
        .scalars()
        .all()
    )
    if existentes:
        return sorted(existentes, key=lambda r: r.numero)

    if (
        modalidade.tipo_disputa == TipoDisputa.CONFRONTO
        and modalidade.formato_chaveamento == FormatoChaveamento.MATA_MATA
    ):
        rodada = await chaveamento_service.gerar_chaveamento_inicial(
            db, modalidade.id, usuario_id=ator_id
        )
        return [rodada]

    rodadas = await rodada_service.gerar_rodadas(db, modalidade.id, usuario_id=ator_id)

    if modalidade.tipo_disputa == TipoDisputa.INDIVIDUAL:
        rodada_ids = [r.id for r in rodadas]
        await agendamento_service.gerar_agendamentos(
            db, modalidade.id, rodada_ids, datetime.now(UTC), usuario_id=ator_id
        )
    return rodadas


# ------------------------------------------------------------------ ficha --

_CACHE_FICHA: dict[tuple, Ficha] = {}


async def obter_ficha(db: AsyncSession, modalidade: Modalidade, nivel: int | None) -> Ficha:
    chave = (modalidade.id, nivel)
    if chave in _CACHE_FICHA:
        return _CACHE_FICHA[chave]

    ficha = await db.scalar(
        select(Ficha).where(Ficha.modalidade_id == modalidade.id, Ficha.nivel == nivel)
    )
    if ficha is None:
        ficha = await db.scalar(
            select(Ficha).where(Ficha.modalidade_id == modalidade.id, Ficha.nivel.is_(None))
        )
    ficha_completa = await ficha_service.obter_ficha_completa(db, ficha.id)
    _CACHE_FICHA[chave] = ficha_completa
    return ficha_completa


def _contribuicao_maxima(c: Criterio) -> float:
    if c.tipo == CriterioTipo.ESCALA:
        return float(max(c.valores_permitidos or [0]))
    if c.tipo == CriterioTipo.BOOLEANO:
        return float(c.pontos or 0)
    if c.tipo == CriterioTipo.CONTADOR:
        maximo = c.max_ocorrencias if c.max_ocorrencias is not None else TETO_CONTADOR_SEM_LIMITE
        return float(c.pontos or 0) * maximo
    return 0.0


def montar_itens_maximo(ficha: Ficha) -> list[ItemLancamentoInput]:
    """Todo criterio positivo no teto, toda penalidade em zero -- o maior
    total matematicamente possivel pra essa ficha."""
    itens = []
    for grupo in ficha.grupos:
        for c in grupo.criterios:
            if c.tipo == CriterioTipo.MODIFICADOR:
                itens.append(ItemLancamentoInput(criterio_id=c.id, aplicado=False))
            elif c.tipo == CriterioTipo.ESCALA:
                itens.append(ItemLancamentoInput(criterio_id=c.id, valor=max(c.valores_permitidos)))
            elif c.categoria == CategoriaCriterio.PENALIDADE:
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=0))
            elif c.tipo == CriterioTipo.BOOLEANO:
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=1))
            else:
                maximo = c.max_ocorrencias if c.max_ocorrencias is not None else TETO_CONTADOR_SEM_LIMITE
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=maximo))
    return itens


def montar_itens_reduzido(ficha: Ficha, rng: random.Random) -> list[ItemLancamentoInput]:
    """Aleatorio, mas com o criterio positivo de maior peso sempre zerado --
    garante matematicamente que o total fica abaixo do maximo (usado pelo
    alvo), nao importa a sorte do resto dos criterios."""
    positivos = [
        c
        for grupo in ficha.grupos
        for c in grupo.criterios
        if c.tipo != CriterioTipo.MODIFICADOR and c.categoria != CategoriaCriterio.PENALIDADE
    ]
    zerar_id = max(positivos, key=_contribuicao_maxima).id if positivos else None

    itens = []
    for grupo in ficha.grupos:
        for c in grupo.criterios:
            if c.tipo == CriterioTipo.MODIFICADOR:
                itens.append(ItemLancamentoInput(criterio_id=c.id, aplicado=False))
            elif c.id == zerar_id:
                if c.tipo == CriterioTipo.ESCALA:
                    itens.append(ItemLancamentoInput(criterio_id=c.id, valor=min(c.valores_permitidos)))
                else:
                    itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=0))
            elif c.categoria == CategoriaCriterio.PENALIDADE:
                if c.tipo == CriterioTipo.ESCALA:
                    itens.append(
                        ItemLancamentoInput(criterio_id=c.id, valor=rng.choice(c.valores_permitidos or [0]))
                    )
                else:
                    maximo = c.max_ocorrencias if c.max_ocorrencias is not None else 2
                    itens.append(
                        ItemLancamentoInput(criterio_id=c.id, ocorrencias=rng.randint(0, min(2, maximo)))
                    )
            elif c.tipo == CriterioTipo.ESCALA:
                valores = sorted(c.valores_permitidos or [0])
                itens.append(ItemLancamentoInput(criterio_id=c.id, valor=rng.choice(valores[:-1] or valores)))
            elif c.tipo == CriterioTipo.BOOLEANO:
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=1 if rng.random() < 0.5 else 0))
            else:
                maximo = c.max_ocorrencias if c.max_ocorrencias is not None else TETO_CONTADOR_SEM_LIMITE
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=rng.randint(0, maximo)))
    return itens


def montar_itens_escala_unica(ficha: Ficha, *, venceu: bool) -> list[ItemLancamentoInput]:
    """Cabo de Guerra / Sumo: ficha de 1 criterio ESCALA so."""
    c = ficha.grupos[0].criterios[0]
    valor = max(c.valores_permitidos) if venceu else min(c.valores_permitidos)
    return [ItemLancamentoInput(criterio_id=c.id, valor=valor)]


def montar_itens_escala_unica_empate(ficha: Ficha) -> list[ItemLancamentoInput]:
    """Mesmo valor pros dois lados -- combate empatado de verdade."""
    c = ficha.grupos[0].criterios[0]
    valor = sorted(c.valores_permitidos)[len(c.valores_permitidos) // 2]
    return [ItemLancamentoInput(criterio_id=c.id, valor=valor)]


def montar_itens_cca_empate(ficha: Ficha) -> list[ItemLancamentoInput]:
    """Itens identicos pros dois lados (sem 'Carro que ficou na frente', sem
    ocorrencia nenhuma) -- combate empatado de verdade (nao conta pra
    nenhum lado, por definicao de decisao COMBATES_VENCIDOS)."""
    itens = []
    for grupo in ficha.grupos:
        for c in grupo.criterios:
            itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=0))
    return itens


def montar_itens_cca(ficha: Ficha, *, venceu: bool, rng: random.Random) -> list[ItemLancamentoInput]:
    """Corrida de Carros: 'Carro que ficou na frente' (+10) decide sozinho,
    o resto e so cor pro relatorio (nunca supera a folga de 10 pontos)."""
    itens = []
    for grupo in ficha.grupos:
        for c in grupo.criterios:
            if c.nome == "Carro que ficou na frente":
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=1 if venceu else 0))
            elif c.nome == "Evitar a colisão":
                maximo = c.max_ocorrencias if c.max_ocorrencias is not None else 3
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=rng.randint(0, maximo)))
            else:
                itens.append(ItemLancamentoInput(criterio_id=c.id, ocorrencias=1 if rng.random() < 0.1 else 0))
    return itens


# -------------------------------------------------------------- lancar --


async def lancar_e_confirmar(
    db: AsyncSession,
    *,
    ficha_id,
    rodada_id,
    tentativa: int,
    equipe_id,
    partida_id,
    itens: list[ItemLancamentoInput],
    ator_id,
):
    dto = LancamentoCreate(
        ficha_id=ficha_id,
        rodada_id=rodada_id,
        tentativa=tentativa,
        equipe_id=equipe_id,
        partida_id=partida_id,
        client_operation_id=uuidlib.uuid4(),
        itens=itens,
    )
    lanc = await lancamento_service.criar_lancamento(db, dto, arbitro_id=ator_id)
    await lancamento_service.confirmar_lancamento(db, lanc.id, usuario_id=ator_id)
    return lanc


# --------------------------------------------------------- individual --


async def pontuar_individual(
    db: AsyncSession, modalidade: Modalidade, *, alvo_por_nivel: dict[int, uuidlib.UUID], ator_id
) -> None:
    rodadas = await preparar_rodadas(db, modalidade, ator_id=ator_id)
    equipes = list(
        (
            await db.execute(
                select(Equipe)
                .join(Inscricao, Inscricao.equipe_id == Equipe.id)
                .where(Inscricao.modalidade_id == modalidade.id)
            )
        )
        .scalars()
        .all()
    )
    print(f"  {len(rodadas)} rodada(s), {len(equipes)} equipe(s)")

    for rodada in rodadas:
        for equipe in equipes:
            ficha = await obter_ficha(db, modalidade, equipe.nivel)
            eh_alvo = equipe.id == alvo_por_nivel.get(equipe.nivel)
            itens = montar_itens_maximo(ficha) if eh_alvo else montar_itens_reduzido(ficha, RNG)
            await lancar_e_confirmar(
                db,
                ficha_id=ficha.id,
                rodada_id=rodada.id,
                tentativa=1,
                equipe_id=equipe.id,
                partida_id=None,
                itens=itens,
                ator_id=ator_id,
            )


# ------------------------------------------------------- confronto liga --


def _planejar_nivel(
    lista: list[Partida], *, alvo_id, todos_os_times: set, pontos_vitoria: float, pontos_empate: float
) -> dict:
    """Decide o resultado (vencedor ou empate) de cada partida do nivel
    inteiramente em memoria antes de gravar qualquer coisa. Um time nao-alvo
    so pode ganhar enquanto sua contagem de vitorias ficar abaixo do teto
    (numero de partidas do alvo menos 1); se os dois lados de uma partida ja
    bateram no teto, a partida empata de verdade em vez de estourar o teto
    pra qualquer um dos dois -- e o que garante o alvo like 1o com folga sem
    risco de gerar lancamento CONFIRMADO (imutavel) errado.

    Tenta ate 50 embaralhamentos antes de desistir (nunca deveria acontecer
    com o teto = partidas_do_alvo - 1, mas e barato conferir em memoria antes
    de tocar no banco).
    """
    matches_alvo = [p for p in lista if alvo_id in (p.equipe_a_id, p.equipe_b_id)]
    cap = max(1, len(matches_alvo) - 1)

    for _tentativa in range(50):
        ordem = list(lista)
        RNG.shuffle(ordem)
        vitorias: dict = defaultdict(int)
        empates: dict = defaultdict(int)
        plano: dict = {}

        for p in ordem:
            a, b = p.equipe_a_id, p.equipe_b_id
            if b is None:
                continue
            if alvo_id in (a, b):
                plano[p.id] = ("vencedor", alvo_id)
                vitorias[alvo_id] += 1
                continue

            pode_a = vitorias[a] < cap
            pode_b = vitorias[b] < cap
            if pode_a and pode_b:
                vencedor = RNG.choice([a, b])
            elif pode_a:
                vencedor = a
            elif pode_b:
                vencedor = b
            else:
                plano[p.id] = ("empate", None)
                empates[a] += 1
                empates[b] += 1
                continue
            plano[p.id] = ("vencedor", vencedor)
            vitorias[vencedor] += 1

        nota_alvo = vitorias[alvo_id] * pontos_vitoria
        maior_outro = 0.0
        for time_id in todos_os_times:
            if time_id == alvo_id:
                continue
            nota = vitorias.get(time_id, 0) * pontos_vitoria + empates.get(time_id, 0) * pontos_empate
            maior_outro = max(maior_outro, nota)

        if nota_alvo > maior_outro:
            return plano

    raise RuntimeError("Nao consegui planejar o nivel sem estourar o teto de vitorias (50 tentativas).")


async def pontuar_todos_contra_todos(
    db: AsyncSession,
    modalidade: Modalidade,
    *,
    sigla: str,
    alvo_por_nivel: dict[int, uuidlib.UUID],
    ator_id,
) -> None:
    rodadas = await preparar_rodadas(db, modalidade, ator_id=ator_id)
    rodada_ids = [r.id for r in rodadas]
    ficha = await obter_ficha(db, modalidade, None)

    partidas = list(
        (await db.execute(select(Partida).where(Partida.rodada_id.in_(rodada_ids))))
        .scalars()
        .all()
    )

    por_nivel: dict[int, list[Partida]] = defaultdict(list)
    for p in partidas:
        por_nivel[p.nivel].append(p)

    equipes_por_nivel: dict[int, set] = defaultdict(set)
    for row in (
        await db.execute(
            select(Equipe.id, Equipe.nivel)
            .join(Inscricao, Inscricao.equipe_id == Equipe.id)
            .where(Inscricao.modalidade_id == modalidade.id)
        )
    ).all():
        equipes_por_nivel[row.nivel].add(row.id)

    print(f"  {len(rodadas)} rodada(s), {len(partidas)} partida(s) em {len(por_nivel)} nivel(is)")

    pontos_vitoria = float(modalidade.pontos_vitoria)
    pontos_empate = float(modalidade.pontos_empate)

    for nivel, lista in por_nivel.items():
        alvo_id = alvo_por_nivel.get(nivel)
        plano = _planejar_nivel(
            lista,
            alvo_id=alvo_id,
            todos_os_times=equipes_por_nivel[nivel],
            pontos_vitoria=pontos_vitoria,
            pontos_empate=pontos_empate,
        )

        for p in lista:
            a, b = p.equipe_a_id, p.equipe_b_id
            if b is None:
                continue
            tipo, vencedor = plano[p.id]

            for tentativa in range(1, modalidade.tentativas_por_rodada + 1):
                if tipo == "empate":
                    lados = (
                        (a, montar_itens_escala_unica_empate(ficha) if sigla == "CDG" else montar_itens_cca_empate(ficha)),
                        (b, montar_itens_escala_unica_empate(ficha) if sigla == "CDG" else montar_itens_cca_empate(ficha)),
                    )
                else:
                    perdedor = b if vencedor == a else a
                    lados = []
                    for equipe_id, venceu in ((vencedor, True), (perdedor, False)):
                        itens = (
                            montar_itens_escala_unica(ficha, venceu=venceu)
                            if sigla == "CDG"
                            else montar_itens_cca(ficha, venceu=venceu, rng=RNG)
                        )
                        lados.append((equipe_id, itens))

                for equipe_id, itens in lados:
                    await lancar_e_confirmar(
                        db,
                        ficha_id=ficha.id,
                        rodada_id=p.rodada_id,
                        tentativa=tentativa,
                        equipe_id=equipe_id,
                        partida_id=p.id,
                        itens=itens,
                        ator_id=ator_id,
                    )


# ------------------------------------------------------------- sumo --


async def pontuar_sumo(db: AsyncSession, modalidade: Modalidade, *, ator_id) -> None:
    await preparar_rodadas(db, modalidade, ator_id=ator_id)
    ficha = await obter_ficha(db, modalidade, None)

    rodadas_geradas = 0
    while True:
        pendentes = list(
            (
                await db.execute(
                    select(Partida)
                    .join(Rodada, Partida.rodada_id == Rodada.id)
                    .where(
                        Rodada.modalidade_id == modalidade.id,
                        Partida.status == PartidaStatus.AGENDADA,
                        Partida.equipe_b_id.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not pendentes:
            break
        rodadas_geradas += 1
        for p in pendentes:
            vencedor = RNG.choice([p.equipe_a_id, p.equipe_b_id])
            perdedor = p.equipe_b_id if vencedor == p.equipe_a_id else p.equipe_a_id
            for tentativa in (1, 2):
                for equipe_id, venceu in ((vencedor, True), (perdedor, False)):
                    itens = montar_itens_escala_unica(ficha, venceu=venceu)
                    await lancar_e_confirmar(
                        db,
                        ficha_id=ficha.id,
                        rodada_id=p.rodada_id,
                        tentativa=tentativa,
                        equipe_id=equipe_id,
                        partida_id=p.id,
                        itens=itens,
                        ator_id=ator_id,
                    )
    print(f"  bracket resolvido em {rodadas_geradas} passada(s)")


# ------------------------------------------------------------------ main --


async def main() -> None:
    async with AsyncSessionLocal() as db:
        ator = await db.scalar(
            select(Usuario).where(Usuario.email == settings.seed_coordenador_email)
        )
        evento = await db.scalar(select(Evento))
        if ator is None or evento is None:
            print("Faltando coordenador seed ou evento -- confira o banco antes de rodar.")
            return

        modalidades_por_nome = {
            m.nome: m
            for m in (
                await db.execute(select(Modalidade).where(Modalidade.evento_id == evento.id))
            )
            .scalars()
            .all()
        }

        # 1) garantir que os 24 times-alvo existem e estao inscritos
        alvo_id_por_sigla_nivel: dict[str, dict[int, uuidlib.UUID]] = defaultdict(dict)
        for sigla, por_nivel in ALVOS.items():
            modalidade = modalidades_por_nome[NOME_MODALIDADE_POR_SIGLA[sigla]]
            for nivel, nome_base in por_nivel.items():
                nome_completo = _nome_completo(nome_base, nivel, sigla)
                equipe = await garantir_equipe_e_inscricao(
                    db, nome=nome_completo, nivel=nivel, modalidade_id=modalidade.id, ator_id=ator.id
                )
                alvo_id_por_sigla_nivel[sigla][nivel] = equipe.id
        await db.flush()
        print("Times-alvo garantidos.\n")

        # 2) pontuar cada modalidade
        for sigla, nome_modalidade in NOME_MODALIDADE_POR_SIGLA.items():
            modalidade = modalidades_por_nome[nome_modalidade]
            print(f"== {nome_modalidade} ({sigla}) ==")
            if sigla == "SUM":
                await pontuar_sumo(db, modalidade, ator_id=ator.id)
            elif modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
                await pontuar_todos_contra_todos(
                    db, modalidade, sigla=sigla, alvo_por_nivel=alvo_id_por_sigla_nivel[sigla], ator_id=ator.id
                )
            else:
                await pontuar_individual(
                    db, modalidade, alvo_por_nivel=alvo_id_por_sigla_nivel[sigla], ator_id=ator.id
                )
            print()

        await db.commit()
        print("Commit feito. Conferindo classificacao real...\n")

        # 3) conferir com o service de verdade (nao o que eu *pretendia*)
        nomes_por_equipe = {
            e.id: e.nome for e in (await db.execute(select(Equipe))).scalars().all()
        }
        for sigla, nome_modalidade in NOME_MODALIDADE_POR_SIGLA.items():
            modalidade = modalidades_por_nome[nome_modalidade]
            classificacao = await consolidacao_service.calcular_classificacao(db, modalidade.id)
            print(f"=== {nome_modalidade} ({sigla}) ===")
            agrupado: dict[int, list[dict]] = defaultdict(list)
            equipe_nivel = {
                e.id: e.nivel
                for e in (
                    await db.execute(
                        select(Equipe)
                        .join(Inscricao, Inscricao.equipe_id == Equipe.id)
                        .where(Inscricao.modalidade_id == modalidade.id)
                    )
                )
                .scalars()
                .all()
            }
            for item in classificacao:
                nivel = equipe_nivel.get(item["equipe_id"])
                agrupado[nivel].append(item)
            for nivel in sorted(agrupado):
                agrupado[nivel].sort(key=lambda r: r["posicao"])
                alvo_id = alvo_id_por_sigla_nivel.get(sigla, {}).get(nivel)
                print(f" Nivel {nivel}:")
                for item in agrupado[nivel][:4]:
                    marca = " <-- ALVO" if item["equipe_id"] == alvo_id else ""
                    nome = nomes_por_equipe.get(item["equipe_id"], "?")
                    print(
                        f"   {item['posicao']}o {nome} "
                        f"(nota={item['nota_final']}, v={item['vitorias']}, "
                        f"e={item['empates']}, d={item['derrotas']}){marca}"
                    )
            print()


if __name__ == "__main__":
    asyncio.run(main())
