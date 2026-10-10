"""Checklist do dia: o que ainda falta preparar em cada modalidade do evento.

So leitura, nada e alterado. Cada item tem um `codigo` estavel (o front usa ele
pra decidir pra qual tela o botao "Resolver" leva) e uma mensagem pronta em
portugues, pensada pra um coordenador sem conhecimento tecnico.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipe import Equipe
from app.models.ficha import Ficha, FichaStatus
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.modalidade import Modalidade, TipoDisputa
from app.models.partida import Partida
from app.models.rodada import Rodada
from app.models.usuario import Papel, Usuario
from app.schemas.checklist import ChecklistItem, ChecklistModalidade, ChecklistOut


def _rotulo_nivel(nivel: int) -> str:
    # Mesmo rotulo do front (lib/nivel.ts): nivel 1 e exibido como ABSOLUTO.
    return "ABSOLUTO" if nivel == 1 else f"Nível {nivel}"


def _lista_niveis(niveis) -> str:
    return ", ".join(_rotulo_nivel(n) for n in sorted(niveis))


def _plural(qtd: int, singular: str, plural: str) -> str:
    return f"{qtd} {singular if qtd == 1 else plural}"


async def _item_ficha(db: AsyncSession, modalidade: Modalidade, niveis: set[int]) -> ChecklistItem:
    publicadas = (
        await db.scalars(
            select(Ficha.nivel).where(
                Ficha.modalidade_id == modalidade.id, Ficha.status == FichaStatus.PUBLICADA
            )
        )
    ).all()
    cobertos = set(publicadas)
    faltando = set() if None in cobertos else niveis - cobertos
    if not publicadas:
        return ChecklistItem(
            codigo="FICHA", ok=False, mensagem="Nenhuma ficha de pontuação publicada."
        )
    if faltando:
        return ChecklistItem(
            codigo="FICHA",
            ok=False,
            mensagem=f"Falta ficha de pontuação publicada para: {_lista_niveis(faltando)}.",
        )
    return ChecklistItem(codigo="FICHA", ok=True, mensagem="Ficha de pontuação publicada.")


def _item_equipes(equipes: list[tuple[Equipe, Inscricao]]) -> ChecklistItem:
    if not equipes:
        return ChecklistItem(codigo="EQUIPES", ok=False, mensagem="Nenhuma equipe inscrita.")
    ausentes = sum(1 for equipe, _ in equipes if not equipe.presente)
    mensagem = f"{_plural(len(equipes), 'equipe inscrita', 'equipes inscritas')}"
    if ausentes:
        mensagem += f" · {_plural(ausentes, 'ausente', 'ausentes')}"
    return ChecklistItem(codigo="EQUIPES", ok=True, mensagem=mensagem + ".")


async def _item_rodadas(db: AsyncSession, modalidade: Modalidade) -> ChecklistItem:
    qtd = await db.scalar(
        select(func.count()).select_from(Rodada).where(Rodada.modalidade_id == modalidade.id)
    )
    if qtd >= modalidade.qtd_rodadas:
        return ChecklistItem(
            codigo="RODADAS",
            ok=True,
            mensagem=f"{_plural(qtd, 'rodada criada', 'rodadas criadas')}.",
        )
    return ChecklistItem(
        codigo="RODADAS",
        ok=False,
        mensagem=f"{qtd} de {modalidade.qtd_rodadas} rodadas criadas.",
    )


def _item_ordem(equipes: list[tuple[Equipe, Inscricao]]) -> ChecklistItem:
    sem_ordem = {
        equipe.nivel for equipe, inscricao in equipes if inscricao.ordem_apresentacao is None
    }
    if sem_ordem:
        return ChecklistItem(
            codigo="ORDEM",
            ok=False,
            mensagem=f"Falta sortear a sequência de competição: {_lista_niveis(sem_ordem)}.",
        )
    return ChecklistItem(codigo="ORDEM", ok=True, mensagem="Sequência de competição sorteada.")


async def _item_confrontos(
    db: AsyncSession, modalidade: Modalidade, niveis: set[int]
) -> ChecklistItem:
    com_partida = set(
        (
            await db.scalars(
                select(Partida.nivel)
                .join(Rodada, Rodada.id == Partida.rodada_id)
                .where(Rodada.modalidade_id == modalidade.id)
                .distinct()
            )
        ).all()
    )
    faltando = niveis - com_partida
    if faltando:
        return ChecklistItem(
            codigo="CONFRONTOS",
            ok=False,
            mensagem=f"Falta montar os confrontos de: {_lista_niveis(faltando)}.",
        )
    return ChecklistItem(
        codigo="CONFRONTOS", ok=True, mensagem="Confrontos montados em todos os níveis."
    )


async def _secao_modalidade(db: AsyncSession, modalidade: Modalidade) -> ChecklistModalidade:
    equipes = list(
        (
            await db.execute(
                select(Equipe, Inscricao)
                .join(Inscricao, Inscricao.equipe_id == Equipe.id)
                .where(Inscricao.modalidade_id == modalidade.id, Equipe.ativo.is_(True))
            )
        )
        .tuples()
        .all()
    )
    niveis = {equipe.nivel for equipe, _ in equipes}

    itens = [await _item_ficha(db, modalidade, niveis), _item_equipes(equipes)]
    if modalidade.tipo_disputa == TipoDisputa.INDIVIDUAL:
        itens.append(await _item_rodadas(db, modalidade))
        itens.append(_item_ordem(equipes))
    else:
        itens.append(await _item_confrontos(db, modalidade, niveis))

    return ChecklistModalidade(
        modalidade_id=modalidade.id,
        nome=modalidade.nome,
        tipo_disputa=modalidade.tipo_disputa,
        itens=itens,
    )


async def _itens_gerais(db: AsyncSession, evento_id: UUID) -> list[ChecklistItem]:
    juizes = await db.scalar(
        select(func.count())
        .select_from(Usuario)
        .where(Usuario.papel == Papel.ARBITRO, Usuario.ativo.is_(True))
    )
    pendentes = await db.scalar(
        select(func.count())
        .select_from(Lancamento)
        .join(Rodada, Rodada.id == Lancamento.rodada_id)
        .join(Modalidade, Modalidade.id == Rodada.modalidade_id)
        .where(Modalidade.evento_id == evento_id, Lancamento.status == LancamentoStatus.PENDENTE)
    )
    return [
        ChecklistItem(
            codigo="JUIZES",
            ok=juizes > 0,
            mensagem=(
                f"{_plural(juizes, 'juiz cadastrado', 'juízes cadastrados')}."
                if juizes
                else "Nenhum juiz cadastrado."
            ),
        ),
        ChecklistItem(
            codigo="NOTAS_PENDENTES",
            ok=pendentes == 0,
            mensagem=(
                "Nenhuma nota esperando confirmação."
                if pendentes == 0
                else f"{_plural(pendentes, 'nota registrada', 'notas registradas')} "
                "esperando confirmação do juiz."
            ),
        ),
    ]


async def gerar_checklist(db: AsyncSession, evento_id: UUID) -> ChecklistOut:
    modalidades = (
        await db.scalars(
            select(Modalidade).where(Modalidade.evento_id == evento_id).order_by(Modalidade.nome)
        )
    ).all()
    return ChecklistOut(
        gerais=await _itens_gerais(db, evento_id),
        modalidades=[await _secao_modalidade(db, m) for m in modalidades],
    )
