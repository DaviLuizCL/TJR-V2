import json
import random
from uuid import UUID

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.chave import Chave, ChaveEquipe
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import DecisaoPartida, FormatoChaveamento, Modalidade, TipoDisputa
from app.models.partida import Partida, PartidaStatus
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.services.audit import registrar_audit_log
from app.services.equipe import obter_equipe
from app.services.modalidade import obter_modalidade
from app.services.rodada import _gerar_pareamento, _rodadas_necessarias

# Nivel com ate esse tanto de equipes vira todos-contra-todos; acima disso
# vira mata-mata (regra combinada com o usuario pras modalidades de combate
# do TJR 2026 - ver gerar_chaveamento_confronto).
LIMITE_EQUIPES_TODOS_CONTRA_TODOS = 5


def _dump(obj) -> dict:
    bruto = {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}
    return json.loads(json.dumps(bruto, default=str))


def _parear_com_bye(equipe_ids: list[UUID]) -> list[tuple[UUID, UUID | None]]:
    """Pareia consecutivamente; se a quantidade for impar, a ultima equipe da
    lista recebe um bye (avanca sem jogar). Funciona pra qualquer quantidade,
    par ou impar, em qualquer rodada do chaveamento.
    """
    pares: list[tuple[UUID, UUID | None]] = []
    i = 0
    while i + 1 < len(equipe_ids):
        pares.append((equipe_ids[i], equipe_ids[i + 1]))
        i += 2
    if i < len(equipe_ids):
        pares.append((equipe_ids[i], None))
    return pares


def _criar_partida(
    rodada_id: UUID,
    equipe_a_id: UUID,
    equipe_b_id: UUID | None,
    nivel: int | None = None,
) -> Partida:
    """Uma partida com equipe_b_id=None e um bye: fecha sozinha, sem jogo.
    So usada pelo lado bracket (gerar_chaveamento_inicial/avancar_se_rodada_completa),
    por isso formato_chaveamento e sempre MATA_MATA aqui.
    """
    return Partida(
        rodada_id=rodada_id,
        equipe_a_id=equipe_a_id,
        equipe_b_id=equipe_b_id,
        nivel=nivel,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        vencedor_id=equipe_a_id if equipe_b_id is None else None,
        status=PartidaStatus.ENCERRADA if equipe_b_id is None else PartidaStatus.AGENDADA,
    )


async def gerar_chaveamento_inicial(
    db: AsyncSession, modalidade_id: UUID, *, usuario_id: UUID
) -> Rodada:
    """Sorteia as equipes inscritas e monta a primeira rodada do chaveamento
    mata-mata. Numero impar de equipes: a ultima do sorteio recebe bye e
    avanca direto.

    Equipes de niveis diferentes nunca se enfrentam: cada nivel corre seu
    proprio chaveamento (bracket separado) dentro da mesma modalidade, todos
    comecando juntos na Rodada 1. Um nivel com so 1 equipe inscrita nao gera
    partida (sem oponente, sem chaveamento possivel nesse nivel).
    """
    modalidade = await obter_modalidade(db, modalidade_id)

    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="MODALIDADE_NAO_E_CONFRONTO",
            mensagem="Chaveamento so pode ser gerado para modalidade de confronto.",
            status_code=422,
        )
    if modalidade.formato_chaveamento != FormatoChaveamento.MATA_MATA:
        raise AppError(
            codigo="FORMATO_CHAVEAMENTO_INVALIDO_PARA_GERAR",
            mensagem="Gerar chaveamento so se aplica a MATA_MATA.",
            status_code=422,
        )

    existente = await db.scalar(select(Rodada).where(Rodada.modalidade_id == modalidade_id))
    if existente is not None:
        raise AppError(
            codigo="CHAVEAMENTO_JA_INICIADO",
            mensagem="Ja existe rodada para esta modalidade; o chaveamento ja foi gerado.",
            status_code=409,
        )

    resultado = await db.execute(
        select(Inscricao.equipe_id, Equipe.nivel)
        .join(Equipe, Inscricao.equipe_id == Equipe.id)
        .where(Inscricao.modalidade_id == modalidade_id)
    )
    linhas = resultado.all()

    equipes_por_nivel: dict[int, list[UUID]] = {}
    for equipe_id, nivel in linhas:
        equipes_por_nivel.setdefault(nivel, []).append(equipe_id)

    grupos_validos = {nivel: ids for nivel, ids in equipes_por_nivel.items() if len(ids) >= 2}
    if not grupos_validos:
        raise AppError(
            codigo="EQUIPES_INSUFICIENTES",
            mensagem="E preciso pelo menos 2 equipes do mesmo nivel pra gerar o chaveamento.",
            status_code=422,
        )

    rodada = Rodada(
        modalidade_id=modalidade_id,
        numero=1,
        modo_horario=ModoHorario.AUTOMATICO,
        status=RodadaStatus.AGENDADA,
    )
    db.add(rodada)
    await db.flush()

    for nivel, ids in grupos_validos.items():
        ids_embaralhados = list(ids)
        random.shuffle(ids_embaralhados)
        for equipe_a_id, equipe_b_id in _parear_com_bye(ids_embaralhados):
            db.add(_criar_partida(rodada.id, equipe_a_id, equipe_b_id, nivel))
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade_id,
        acao="GERAR_CHAVEAMENTO",
        antes=None,
        depois={"rodada_id": str(rodada.id), "qtd_equipes": len(linhas)},
    )

    return rodada


async def criar_partida_manual(
    db: AsyncSession,
    modalidade_id: UUID,
    equipe_a_id: UUID,
    equipe_b_id: UUID | None,
    *,
    usuario_id: UUID,
) -> Partida:
    """Monta o chaveamento no braço, um confronto de cada vez: o coordenador
    escolhe as duas equipes (ou so uma, pra dar bye) e salva -- sem precisar
    decidir o nivel inteiro de uma so vez, nem travar formato_chaveamento
    pra nada. Assim que a partida existe, ja aparece pro arbitro no fluxo
    Pontuar de graca (PontuarCombatePage so olha pra Partida existente,
    nao pra como ela foi criada).

    A rodada-alvo e calculada, nao mais fixa em numero=1: e a rodada seguinte
    a ultima que esse nivel ja tem partida, MAS so avanca de rodada quando
    essa ultima rodada foi de fase de grupos (TODOS_CONTRA_TODOS) -- se ja
    for uma rodada de mata-mata (outra chamada manual anterior, ainda
    montando o mesmo mata-mata), reaproveita a mesma rodada em vez de abrir
    outra. Isso cobre os dois casos reais: (a) nivel que nunca teve chave,
    mata-mata 100% manual desde o inicio -- toda chamada cai na Rodada 1,
    igual sempre foi; (b) nivel que passou por fase de grupos (rodadas 1..N
    de TODOS_CONTRA_TODOS) -- a primeira chamada pos-grupos abre a Rodada
    N+1 (o mata-mata), e as chamadas seguintes (outros pares da mesma
    primeira rodada do mata-mata) reaproveitam essa Rodada N+1. Da segunda
    rodada do mata-mata em diante (ex.: semifinal->final), o avanco
    automatico (avancar_se_rodada_completa) cuida sozinho, sem precisar de
    nova chamada manual. Convive com gerar_chaveamento_confronto: um nivel
    montado por aqui fica de fora quando o automatico rodar pros demais
    niveis da mesma modalidade (ver gerar_chaveamento_confronto).
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="MODALIDADE_NAO_E_CONFRONTO",
            mensagem="Chaveamento so pode ser gerado para modalidade de confronto.",
            status_code=422,
        )

    if equipe_b_id is not None and equipe_a_id == equipe_b_id:
        raise AppError(
            codigo="EQUIPES_IGUAIS",
            mensagem="As duas equipes de uma partida precisam ser diferentes.",
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

    nivel = equipe_a.nivel
    maior_numero_do_nivel = await db.scalar(
        select(func.max(Rodada.numero))
        .select_from(Partida)
        .join(Rodada, Partida.rodada_id == Rodada.id)
        .where(Rodada.modalidade_id == modalidade_id, Partida.nivel == nivel)
    )
    if maior_numero_do_nivel is None:
        numero_alvo = 1
    else:
        ultima_e_mata_mata = await db.scalar(
            select(Partida.id)
            .join(Rodada, Partida.rodada_id == Rodada.id)
            .where(
                Rodada.modalidade_id == modalidade_id,
                Rodada.numero == maior_numero_do_nivel,
                Partida.nivel == nivel,
                Partida.formato_chaveamento == FormatoChaveamento.MATA_MATA,
            )
            .limit(1)
        )
        numero_alvo = (
            maior_numero_do_nivel if ultima_e_mata_mata is not None else (maior_numero_do_nivel + 1)
        )

    rodada = await _obter_ou_criar_rodada(db, modalidade_id, numero_alvo, {})

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

    partida = _criar_partida(rodada.id, equipe_a.id, equipe_b_id, equipe_a.nivel)
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


async def _obter_ou_criar_rodada(
    db: AsyncSession, modalidade_id: UUID, numero: int, cache: dict[int, Rodada]
) -> Rodada:
    """Reaproveita a `Rodada` de `numero` se ja existir (cache local da chamada,
    senao consulta o banco), ou cria uma nova -- e o que permite bracket, liga
    e fase de grupos dividirem a mesma sequencia de `Rodada.numero` de uma
    modalidade sem conflito (cada `Partida` carrega seu proprio nivel/chave).
    """
    rodada = cache.get(numero)
    if rodada is None:
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
    cache[numero] = rodada
    return rodada


async def gerar_fase_de_grupos(
    db: AsyncSession, modalidade_id: UUID, *, usuario_id: UUID
) -> list[Rodada]:
    """Gera o round-robin (mesmo metodo do circulo do returno normal,
    `_gerar_pareamento`/`_rodadas_necessarias`) dentro de cada `Chave`
    pendente da modalidade -- equivalente ao bloco `niveis_liga` de
    `gerar_chaveamento_confronto`, so que agrupado por `chave_id` em vez de
    `nivel`. Cada chave joga so contra si mesma (nunca cruza com outra
    chave); a partida fica `formato_chaveamento=TODOS_CONTRA_TODOS` (chave e
    fisicamente um returno pequeno) e carrega `chave_id` pra distinguir de
    mata-mata (automatico ou manual) dentro da mesma modalidade.

    Idempotente: chave que ja tem qualquer partida (chamada anterior) e
    ignorada -- convive com o coordenador gerando aos poucos, conforme cria
    novas chaves. Depois que a fase de grupos fecha, o mata-mata e montado na
    mao via `criar_partida_manual` (ver docstring dela).
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="MODALIDADE_NAO_E_CONFRONTO",
            mensagem="Fase de grupos so pode ser gerada para modalidade de confronto.",
            status_code=422,
        )

    chaves = list(
        (await db.execute(select(Chave).where(Chave.modalidade_id == modalidade_id)))
        .scalars()
        .all()
    )
    if not chaves:
        raise AppError(
            codigo="NENHUMA_CHAVE_PENDENTE",
            mensagem="Nenhuma chave cadastrada para esta modalidade.",
            status_code=422,
        )

    chaves_com_partida = {
        chave_id
        for (chave_id,) in (
            await db.execute(
                select(Partida.chave_id)
                .join(Rodada, Partida.rodada_id == Rodada.id)
                .where(Rodada.modalidade_id == modalidade_id, Partida.chave_id.is_not(None))
                .distinct()
            )
        ).all()
    }
    chaves_pendentes = [c for c in chaves if c.id not in chaves_com_partida]
    if not chaves_pendentes:
        raise AppError(
            codigo="NENHUMA_CHAVE_PENDENTE",
            mensagem="Todas as chaves desta modalidade ja tem partida gerada.",
            status_code=422,
        )

    equipes_por_chave: dict[UUID, list[UUID]] = {}
    for chave in chaves_pendentes:
        ids = list(
            (
                await db.execute(
                    select(ChaveEquipe.equipe_id).where(ChaveEquipe.chave_id == chave.id)
                )
            )
            .scalars()
            .all()
        )
        if len(ids) < 2:
            raise AppError(
                codigo="CHAVE_SEM_EQUIPES_SUFICIENTES",
                mensagem=f"A chave '{chave.nome}' precisa de pelo menos 2 equipes.",
                status_code=422,
            )
        equipes_por_chave[chave.id] = ids

    nivel_por_chave = {chave.id: chave.nivel for chave in chaves_pendentes}
    rodadas_por_numero: dict[int, Rodada] = {}
    maximo = max(_rodadas_necessarias(len(ids)) for ids in equipes_por_chave.values())
    for numero in range(1, maximo + 1):
        rodada = await _obter_ou_criar_rodada(db, modalidade_id, numero, rodadas_por_numero)
        for chave_id, ids in equipes_por_chave.items():
            if numero > _rodadas_necessarias(len(ids)):
                continue
            for equipe_a_id, equipe_b_id in _gerar_pareamento(ids, numero):
                db.add(
                    Partida(
                        rodada_id=rodada.id,
                        equipe_a_id=equipe_a_id,
                        equipe_b_id=equipe_b_id,
                        nivel=nivel_por_chave[chave_id],
                        chave_id=chave_id,
                        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
                        status=PartidaStatus.AGENDADA,
                    )
                )
        await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade_id,
        acao="GERAR_FASE_DE_GRUPOS",
        antes=None,
        depois={"chaves": [str(c.id) for c in chaves_pendentes]},
    )

    return sorted(rodadas_por_numero.values(), key=lambda r: r.numero)


async def gerar_chaveamento_confronto(
    db: AsyncSession, modalidade_id: UUID, *, usuario_id: UUID
) -> list[Rodada]:
    """Ponto de entrada unico pra iniciar uma modalidade de confronto.

    Antes, `gerar_chaveamento_inicial` (bracket) e `gerar_rodadas` (returno)
    exigiam que a modalidade inteira estivesse num formato so - mas a regra
    real (TJR 2026) precisa decidir por nivel: <=5 equipes inscritas nesse
    nivel = todos-contra-todos, 6+ = mata-mata. `modalidade.formato_chaveamento`
    continua existindo, so muda de sentido: None = decisao automatica por
    nivel (o caso comum agora); um valor explicito forca esse formato pra
    TODOS os niveis da modalidade, ignorando a contagem (escape manual, ex.:
    coordenador quer garantir mata-mata mesmo com poucas equipes).

    Reaproveita a mesma mecanica ja usada por `gerar_chaveamento_inicial`
    (bracket, `_criar_partida`/`_parear_com_bye`) e por `gerar_rodadas`
    (returno, `_gerar_pareamento`/`_rodadas_necessarias`) - so que agora cada
    uma opera so no subconjunto de niveis que decidiu usar aquele formato,
    dentro da MESMA sequencia de `Rodada.numero` (um nivel bracket e um
    nivel returno podem, por exemplo, dividir a Rodada 1 sem conflito,
    porque toda partida ja carrega `nivel`).
    """
    modalidade = await obter_modalidade(db, modalidade_id)

    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="MODALIDADE_NAO_E_CONFRONTO",
            mensagem="Chaveamento so pode ser gerado para modalidade de confronto.",
            status_code=422,
        )

    resultado = await db.execute(
        select(Inscricao.equipe_id, Equipe.nivel)
        .join(Equipe, Inscricao.equipe_id == Equipe.id)
        .where(Inscricao.modalidade_id == modalidade_id)
        .order_by(Inscricao.equipe_id)
    )
    equipes_por_nivel: dict[int, list[UUID]] = {}
    for equipe_id, nivel in resultado.all():
        equipes_por_nivel.setdefault(nivel, []).append(equipe_id)

    # Nivel que ja tem QUALQUER partida (montada na mao via
    # criar_partida_manual, ou por uma chamada anterior deste mesmo
    # gerador) fica de fora -- nao reembaralha nem duplica o que ja existe.
    # E o que deixa esse gerador conviver com montagem manual de outro
    # nivel da mesma modalidade (ver criar_partida_manual).
    niveis_com_partida = {
        nivel
        for (nivel,) in (
            await db.execute(
                select(Partida.nivel)
                .join(Rodada, Partida.rodada_id == Rodada.id)
                .where(Rodada.modalidade_id == modalidade_id)
                .distinct()
            )
        ).all()
    }

    niveis_bracket: dict[int, list[UUID]] = {}
    niveis_liga: dict[int, list[UUID]] = {}
    for nivel, ids in equipes_por_nivel.items():
        if len(ids) < 2 or nivel in niveis_com_partida:
            continue
        formato = modalidade.formato_chaveamento or (
            FormatoChaveamento.TODOS_CONTRA_TODOS
            if len(ids) <= LIMITE_EQUIPES_TODOS_CONTRA_TODOS
            else FormatoChaveamento.MATA_MATA
        )
        if formato == FormatoChaveamento.MATA_MATA:
            niveis_bracket[nivel] = ids
        else:
            niveis_liga[nivel] = ids

    if not niveis_bracket and not niveis_liga:
        if niveis_com_partida:
            raise AppError(
                codigo="CHAVEAMENTO_JA_INICIADO",
                mensagem="Ja existe rodada para esta modalidade; o chaveamento ja foi gerado.",
                status_code=409,
            )
        raise AppError(
            codigo="EQUIPES_INSUFICIENTES",
            mensagem="E preciso pelo menos 2 equipes do mesmo nivel pra gerar o chaveamento.",
            status_code=422,
        )

    rodadas_por_numero: dict[int, Rodada] = {}

    if niveis_bracket:
        rodada1 = await _obter_ou_criar_rodada(db, modalidade_id, 1, rodadas_por_numero)
        for nivel, ids in niveis_bracket.items():
            embaralhado = list(ids)
            random.shuffle(embaralhado)
            for equipe_a_id, equipe_b_id in _parear_com_bye(embaralhado):
                db.add(_criar_partida(rodada1.id, equipe_a_id, equipe_b_id, nivel))
        await db.flush()

    if niveis_liga:
        maximo = max(_rodadas_necessarias(len(ids)) for ids in niveis_liga.values())
        for numero in range(1, maximo + 1):
            rodada = await _obter_ou_criar_rodada(db, modalidade_id, numero, rodadas_por_numero)
            for nivel, ids in niveis_liga.items():
                if numero > _rodadas_necessarias(len(ids)):
                    continue
                for equipe_a_id, equipe_b_id in _gerar_pareamento(ids, numero):
                    db.add(
                        Partida(
                            rodada_id=rodada.id,
                            equipe_a_id=equipe_a_id,
                            equipe_b_id=equipe_b_id,
                            nivel=nivel,
                            formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
                            status=PartidaStatus.AGENDADA,
                        )
                    )
            await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade_id,
        acao="GERAR_CHAVEAMENTO",
        antes=None,
        depois={
            "niveis_bracket": sorted(niveis_bracket),
            "niveis_liga": sorted(niveis_liga),
        },
    )

    return sorted(rodadas_por_numero.values(), key=lambda r: r.numero)


async def avancar_se_rodada_completa(
    db: AsyncSession, rodada_id: UUID, *, usuario_id: UUID
) -> Rodada | None:
    """Se todas as partidas da rodada ja tem vencedor, gera a proxima rodada
    pareando os vencedores na ordem em que as partidas foram criadas
    (preserva o formato do chaveamento).

    Cada nivel corre seu proprio chaveamento, independente dos outros: as
    partidas da rodada sao agrupadas por `nivel`, e o gate de "esta tudo
    fechado" e avaliado por grupo, nao pela rodada inteira - um nivel cujas
    partidas ja fecharam avanca mesmo com outro nivel (maior, ou so mais
    lento pra ser pontuado) ainda em aberto. Como o avanco automatico e
    chamado de dentro de cada confirmacao de lancamento (uma partida por
    vez), a proxima rodada pode ja existir com o nivel de outra chamada
    anterior - por isso reaproveita a rodada de `numero + 1` se ela ja foi
    criada, em vez de sempre abrir uma nova (o que duplicaria rodadas), e
    pula nivel que ja tenha partida la (idempotente a chamadas repetidas).
    Um nivel que ja chegou ao campeao simplesmente nao recebe mais partida.
    So nao ha nada novo pra gerar quando NENHUM nivel pendente fechou ainda.
    """
    rodada = await db.get(Rodada, rodada_id)
    modalidade = await db.get(Modalidade, rodada.modalidade_id)

    resultado = await db.execute(
        select(Partida).where(Partida.rodada_id == rodada_id).order_by(Partida.criado_em)
    )
    partidas = list(resultado.scalars().all())

    partidas_por_nivel: dict[int | None, list[Partida]] = {}
    for partida in partidas:
        partidas_por_nivel.setdefault(partida.nivel, []).append(partida)

    proxima_rodada = await db.scalar(
        select(Rodada).where(
            Rodada.modalidade_id == modalidade.id, Rodada.numero == rodada.numero + 1
        )
    )
    niveis_ja_avancados: set[int | None] = set()
    if proxima_rodada is not None:
        resultado_niveis = await db.execute(
            select(Partida.nivel).where(Partida.rodada_id == proxima_rodada.id).distinct()
        )
        niveis_ja_avancados = {nivel for (nivel,) in resultado_niveis.all()}

    pares: list[tuple[UUID, UUID | None, int | None]] = []

    for nivel, partidas_do_nivel in partidas_por_nivel.items():
        if nivel in niveis_ja_avancados:
            continue
        if any(p.status != PartidaStatus.ENCERRADA for p in partidas_do_nivel):
            continue
        vencedores = [p.vencedor_id for p in partidas_do_nivel]
        if len(vencedores) <= 1:
            continue
        pares.extend((a, b, nivel) for a, b in _parear_com_bye(vencedores))

    if not pares:
        return None

    if proxima_rodada is None:
        proxima_rodada = Rodada(
            modalidade_id=modalidade.id,
            numero=rodada.numero + 1,
            modo_horario=ModoHorario.AUTOMATICO,
            status=RodadaStatus.AGENDADA,
        )
        db.add(proxima_rodada)
        await db.flush()

    for equipe_a_id, equipe_b_id, nivel in pares:
        db.add(_criar_partida(proxima_rodada.id, equipe_a_id, equipe_b_id, nivel))
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="rodada",
        entidade_id=proxima_rodada.id,
        acao="AVANCAR_CHAVEAMENTO",
        antes=None,
        depois={"numero": proxima_rodada.numero},
    )

    return proxima_rodada


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
    - Mata-mata: ao fechar com vencedor, tenta avancar a rodada.
      Todos-contra-todos nunca tenta avancar rodada, ja que o returno inteiro
      e pre-gerado de uma vez, sem chaveamento dinamico.

    Nao faz nada fora de confronto, em formato sem essas regras, ou enquanto
    algum dos dois lados nao tiver confirmado todos os combates da partida.
    """
    if lancamento.partida_id is None:
        return

    partida = await db.get(Partida, lancamento.partida_id)
    if partida is None or partida.status in (PartidaStatus.ENCERRADA, PartidaStatus.EMPATADA):
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

    if pontuacao_a == pontuacao_b:
        if not eh_todos_contra_todos:
            return
        partida.status = PartidaStatus.EMPATADA
        await db.flush()
        await registrar_audit_log(
            db,
            usuario_id=usuario_id,
            entidade="partida",
            entidade_id=partida.id,
            acao="EMPATAR",
            antes=None,
            depois={"status": "EMPATADA", "pontuacao_a": pontuacao_a, "pontuacao_b": pontuacao_b},
        )
        return

    vencedor_id = equipe_a_id if pontuacao_a > pontuacao_b else equipe_b_id

    partida.status = PartidaStatus.ENCERRADA
    partida.vencedor_id = vencedor_id
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="partida",
        entidade_id=partida.id,
        acao="ENCERRAR",
        antes=None,
        depois={
            "vencedor_id": str(vencedor_id),
            "pontuacao_a": pontuacao_a,
            "pontuacao_b": pontuacao_b,
        },
    )

    if eh_chaveamento:
        await avancar_se_rodada_completa(db, rodada.id, usuario_id=usuario_id)


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
