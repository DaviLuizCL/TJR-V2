"""Telas publicas (sem login), pensadas pro professor e pra torcida no ginasio.

Nada aqui expoe nota: o ranking continua so pra staff. A sequencia publica diz
so quem ja se apresentou em cada rodada e quem e a proxima.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.modalidade import Modalidade, TipoDisputa
from app.models.rodada import Rodada
from app.services.evento import obter_evento
from app.services.ordem_apresentacao import listar_sequencia


@dataclass
class EquipeInscritaPublica:
    nome: str
    nivel: int
    modalidades: list[str]


@dataclass
class EquipePublica:
    nome: str
    posicao: int
    presente: bool
    rodadas_competidas: list[int]
    proxima: bool
    equipes_na_frente: int | None = None


@dataclass
class NivelPublico:
    nivel: int
    equipes: list[EquipePublica]


@dataclass
class ModalidadePublica:
    id: UUID
    nome: str
    rodadas: list[int]
    niveis: list[NivelPublico]


async def _rodadas_competidas_por_equipe(
    db: AsyncSession, modalidade: Modalidade, rodadas: list[Rodada]
) -> dict[UUID, set[int]]:
    """Rodada conta como competida quando a equipe tem lancamento nao anulado
    em todas as tentativas dela (PENDENTE conta: a equipe ja se apresentou)."""
    numero_por_rodada = {rodada.id: rodada.numero for rodada in rodadas}
    if not numero_por_rodada:
        return {}
    linhas = await db.execute(
        select(Lancamento.equipe_id, Lancamento.rodada_id, Lancamento.tentativa).where(
            Lancamento.rodada_id.in_(numero_por_rodada),
            Lancamento.status != LancamentoStatus.ANULADO,
        )
    )
    tentativas: dict[tuple[UUID, UUID], set[int]] = {}
    for equipe_id, rodada_id, tentativa in linhas.tuples():
        tentativas.setdefault((equipe_id, rodada_id), set()).add(tentativa)

    necessarias = set(range(1, (modalidade.tentativas_por_rodada or 1) + 1))
    competidas: dict[UUID, set[int]] = {}
    for (equipe_id, rodada_id), feitas in tentativas.items():
        if necessarias <= feitas:
            competidas.setdefault(equipe_id, set()).add(numero_por_rodada[rodada_id])
    return competidas


async def _evento_unico_id(db: AsyncSession) -> UUID:
    """Sistema e exclusivo do TJR, com um evento so (criar_evento recusa o
    segundo): o link publico nao carrega id de evento."""
    evento_id = await db.scalar(select(Evento.id).order_by(Evento.criado_em).limit(1))
    if evento_id is None:
        raise AppError(
            codigo="EVENTO_NAO_ENCONTRADO", mensagem="Evento nao encontrado.", status_code=404
        )
    return evento_id


async def sequencia_publica(db: AsyncSession) -> list[ModalidadePublica]:
    return await sequencia_publica_do_evento(db, await _evento_unico_id(db))


async def equipes_publicas(db: AsyncSession) -> list[EquipeInscritaPublica]:
    return await equipes_publicas_do_evento(db, await _evento_unico_id(db))


async def equipes_publicas_do_evento(
    db: AsyncSession, evento_id: UUID
) -> list[EquipeInscritaPublica]:
    """Toda equipe ativa com as modalidades do evento em que esta inscrita, pro
    professor conferir o cadastro. Equipe sem modalidade nenhuma aparece tambem:
    e justamente o caso que ele precisa ver pra pedir correcao."""
    equipes = (
        await db.scalars(
            select(Equipe).where(Equipe.ativo.is_(True)).order_by(Equipe.nivel, Equipe.nome)
        )
    ).all()
    inscricoes = await db.execute(
        select(Inscricao.equipe_id, Modalidade.nome)
        .join(Modalidade, Modalidade.id == Inscricao.modalidade_id)
        .where(Modalidade.evento_id == evento_id)
        .order_by(Modalidade.nome)
    )
    modalidades_por_equipe: dict[UUID, list[str]] = {}
    for equipe_id, nome in inscricoes.tuples():
        modalidades_por_equipe.setdefault(equipe_id, []).append(nome)
    return [
        EquipeInscritaPublica(
            nome=equipe.nome,
            nivel=equipe.nivel,
            modalidades=modalidades_por_equipe.get(equipe.id, []),
        )
        for equipe in equipes
    ]


async def sequencia_publica_do_evento(db: AsyncSession, evento_id: UUID) -> list[ModalidadePublica]:
    await obter_evento(db, evento_id)
    modalidades = (
        await db.scalars(
            select(Modalidade)
            .where(
                Modalidade.evento_id == evento_id,
                Modalidade.tipo_disputa == TipoDisputa.INDIVIDUAL,
            )
            .order_by(Modalidade.nome)
        )
    ).all()

    resultado = []
    for modalidade in modalidades:
        rodadas = list(
            (
                await db.scalars(
                    select(Rodada)
                    .where(Rodada.modalidade_id == modalidade.id)
                    .order_by(Rodada.numero)
                )
            ).all()
        )
        numeros = [rodada.numero for rodada in rodadas]
        competidas = await _rodadas_competidas_por_equipe(db, modalidade, rodadas)

        niveis = []
        for nivel in await listar_sequencia(db, modalidade.id):
            equipes = [
                EquipePublica(
                    nome=equipe.nome,
                    posicao=posicao,
                    presente=equipe.presente,
                    rodadas_competidas=sorted(competidas.get(equipe.equipe_id, set())),
                    proxima=False,
                )
                for posicao, equipe in enumerate(nivel.equipes, start=1)
            ]
            _calcular_fila(equipes, numeros)
            niveis.append(NivelPublico(nivel=nivel.nivel, equipes=equipes))

        resultado.append(
            ModalidadePublica(
                id=modalidade.id, nome=modalidade.nome, rodadas=numeros, niveis=niveis
            )
        )
    return resultado


def _calcular_fila(equipes: list[EquipePublica], rodadas: list[int]) -> None:
    """Mesma fila do Pontuar: a rodada mais atrasada primeiro e, dentro dela,
    a ordem da sequencia. Equipe ausente fica fora da fila (nunca e a proxima)
    e quem ja fez todas as rodadas tambem."""
    fila = []
    for equipe in equipes:
        pendente = next((n for n in rodadas if n not in equipe.rodadas_competidas), None)
        if equipe.presente and pendente is not None:
            fila.append((pendente, equipe.posicao, equipe))
    fila.sort(key=lambda item: (item[0], item[1]))
    for indice, (_, _, equipe) in enumerate(fila):
        equipe.equipes_na_frente = indice
        equipe.proxima = indice == 0
