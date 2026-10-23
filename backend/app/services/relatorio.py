from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.ficha import Ficha, FichaStatus
from app.models.lancamento import Lancamento, LancamentoStatus
from app.models.modalidade import FormatoChaveamento, Modalidade, TipoDisputa
from app.models.partida import Partida
from app.models.rodada import Rodada
from app.services.consolidacao import calcular_classificacao
from app.services.evento import obter_evento
from app.services.modalidade import obter_modalidade
from app.services.nivel import rotulo_nivel

_FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")


@dataclass
class ConfrontoResumo:
    rodada: int
    nivel: int | None
    equipe_a: str
    pontos_a: Decimal
    equipe_b: str | None
    pontos_b: Decimal
    vencedor: str | None


@dataclass
class PontuacaoModalidade:
    rodadas: list[tuple[UUID, int]] = field(default_factory=list)
    nota_por_rodada: dict[tuple[UUID, UUID], Decimal] = field(default_factory=dict)
    pontos_por_equipe: dict[UUID, Decimal] = field(default_factory=dict)
    confrontos: list[ConfrontoResumo] = field(default_factory=list)


def _formatar_pontos(valor: Decimal) -> str:
    """30.00 -> "30", 12.50 -> "12.5" (Numeric do banco vem com casas fixas)."""
    return f"{Decimal(valor).normalize():f}"


async def _carregar_pontuacao(db: AsyncSession, modalidade: Modalidade) -> PontuacaoModalidade:
    """Nota de cada rodada (individual) ou placar de cada confronto, so com
    lancamento CONFIRMADO de ficha nao DEPRECADA - mesmo filtro da
    consolidacao, pra o numero do relatorio bater com a nota final.
    """
    rodadas = (
        await db.execute(
            select(Rodada.id, Rodada.numero)
            .where(Rodada.modalidade_id == modalidade.id)
            .order_by(Rodada.numero)
        )
    ).all()
    numero_da_rodada = {rodada_id: numero for rodada_id, numero in rodadas}
    lancamentos = (
        (
            await db.scalars(
                select(Lancamento)
                .join(Ficha, Lancamento.ficha_id == Ficha.id)
                .where(
                    Lancamento.rodada_id.in_(numero_da_rodada),
                    Lancamento.status == LancamentoStatus.CONFIRMADO,
                    Ficha.status != FichaStatus.DEPRECADA,
                )
            )
        ).all()
        if rodadas
        else []
    )

    pontuacao = PontuacaoModalidade()
    if modalidade.tipo_disputa == TipoDisputa.INDIVIDUAL:
        pontuacao.rodadas = [(rodada_id, numero) for rodada_id, numero in rodadas]
        # Mesma regra da consolidacao: vale o maior total da equipe na rodada.
        for lancamento in lancamentos:
            chave = (lancamento.equipe_id, lancamento.rodada_id)
            total = Decimal(lancamento.total)
            if chave not in pontuacao.nota_por_rodada or total > pontuacao.nota_por_rodada[chave]:
                pontuacao.nota_por_rodada[chave] = total
        return pontuacao

    pontos_por_partida_equipe: dict[tuple[UUID, UUID], Decimal] = {}
    for lancamento in lancamentos:
        if lancamento.partida_id is None:
            continue
        chave = (lancamento.partida_id, lancamento.equipe_id)
        total = Decimal(lancamento.total)
        pontos_por_partida_equipe[chave] = (
            pontos_por_partida_equipe.get(chave, Decimal("0")) + total
        )
        pontuacao.pontos_por_equipe[lancamento.equipe_id] = (
            pontuacao.pontos_por_equipe.get(lancamento.equipe_id, Decimal("0")) + total
        )

    partidas = (
        (
            await db.scalars(
                select(Partida)
                .where(Partida.rodada_id.in_(numero_da_rodada))
                .order_by(Partida.nivel, Partida.criado_em)
            )
        ).all()
        if rodadas
        else []
    )
    ids_equipes = {e for p in partidas for e in (p.equipe_a_id, p.equipe_b_id) if e is not None}
    nomes = (
        {
            e.id: e.nome
            for e in (await db.scalars(select(Equipe).where(Equipe.id.in_(ids_equipes)))).all()
        }
        if ids_equipes
        else {}
    )
    for partida in sorted(partidas, key=lambda p: numero_da_rodada[p.rodada_id]):
        pontuacao.confrontos.append(
            ConfrontoResumo(
                rodada=numero_da_rodada[partida.rodada_id],
                nivel=partida.nivel,
                equipe_a=nomes.get(partida.equipe_a_id, "-"),
                pontos_a=pontos_por_partida_equipe.get(
                    (partida.id, partida.equipe_a_id), Decimal("0")
                ),
                equipe_b=nomes.get(partida.equipe_b_id) if partida.equipe_b_id else None,
                pontos_b=pontos_por_partida_equipe.get(
                    (partida.id, partida.equipe_b_id), Decimal("0")
                ),
                vencedor=nomes.get(partida.vencedor_id) if partida.vencedor_id else None,
            )
        )
    return pontuacao


def _calcular_gerado_em() -> datetime:
    return datetime.now(UTC).astimezone(_FUSO_FORTALEZA)


def _formatar_metrica_classificacao(modalidade: Modalidade, item: dict) -> str:
    """Mesma logica de exibicao do RankingOut (ranking.py): o formato do
    numero depende do formato_chaveamento do NIVEL dessa equipe (gravado no
    proprio item por calcular_classificacao, ja que niveis diferentes da
    mesma modalidade podem estar em formatos diferentes), nao mais de um
    campo unico da modalidade inteira.
    """
    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        if item["formato_chaveamento"] == FormatoChaveamento.MATA_MATA:
            return f"{item['vitorias']}V {item['derrotas']}D"
        if item["formato_chaveamento"] == FormatoChaveamento.TODOS_CONTRA_TODOS:
            return (
                f"{item['nota_final']} pts "
                f"({item['vitorias']}V {item['empates']}E {item['derrotas']}D)"
            )
    return str(item["nota_final"])


async def _carregar_dados_modalidade(
    db: AsyncSession, modalidade: Modalidade
) -> tuple[list[dict], dict[UUID, Equipe]]:
    """Busca a classificacao de uma modalidade e as equipes envolvidas - dado
    cru, sem nenhuma formatacao de PDF, reutilizado tanto pelo relatorio de
    uma unica modalidade quanto pelo relatorio geral do evento (uma chamada
    por modalidade).
    """
    classificacao = await calcular_classificacao(db, modalidade.id)
    equipe_ids = {item["equipe_id"] for item in classificacao}

    equipes_por_id: dict[UUID, Equipe] = {}
    if equipe_ids:
        resultado_equipes = await db.execute(select(Equipe).where(Equipe.id.in_(equipe_ids)))
        equipes_por_id = {e.id: e for e in resultado_equipes.scalars().all()}

    return classificacao, equipes_por_id


def _montar_secao_modalidade(
    estilos: StyleSheet1,
    modalidade: Modalidade,
    classificacao: list[dict],
    equipes_por_id: dict[UUID, Equipe],
    pontuacao: PontuacaoModalidade | None = None,
) -> list:
    """Monta os flowables de classificacao de uma modalidade - o corpo do
    relatorio, sem cabecalho de documento. Reutilizado pelo relatorio de uma
    unica modalidade e pelo relatorio geral do evento (uma secao por
    modalidade, separadas por quebra de pagina).

    Uma sub-secao por nivel, cada uma com seu proprio titulo e tabela -
    equipes de niveis diferentes nunca competem entre si (regra invioravel 9,
    calcular_classificacao ja numera a posicao separadamente por nivel),
    entao misturar tudo numa tabela so so dificultava achar "quem ganhou o
    nivel X" no meio de dezenas de linhas.
    """
    elementos: list = []

    elementos.append(Paragraph("Classificacao", estilos["Heading2"]))

    grupos_por_nivel: dict[int | None, list[tuple[dict, Equipe | None]]] = {}
    for item in classificacao:
        equipe = equipes_por_id.get(item["equipe_id"])
        nivel = equipe.nivel if equipe else None
        grupos_por_nivel.setdefault(nivel, []).append((item, equipe))

    for nivel in sorted(grupos_por_nivel, key=lambda n: (n is None, n)):
        elementos.append(
            Paragraph(
                rotulo_nivel(nivel) if nivel is not None else "Nivel nao identificado",
                estilos["Heading3"],
            )
        )
        elementos.append(
            _tabela(_linhas_classificacao(modalidade, grupos_por_nivel[nivel], pontuacao))
        )
        elementos.append(Spacer(1, 0.5 * cm))

    if pontuacao and pontuacao.confrontos:
        elementos.append(Paragraph("Confrontos", estilos["Heading2"]))
        linhas = [["Rodada", "Equipe A", "Placar", "Equipe B", "Vencedor"]]
        for c in pontuacao.confrontos:
            linhas.append(
                [
                    str(c.rodada),
                    c.equipe_a,
                    f"{_formatar_pontos(c.pontos_a)} x {_formatar_pontos(c.pontos_b)}"
                    if c.equipe_b
                    else "-",
                    c.equipe_b or "(bye)",
                    c.vencedor or "-",
                ]
            )
        elementos.append(_tabela(linhas))
        elementos.append(Spacer(1, 0.5 * cm))

    return elementos


def _linhas_classificacao(
    modalidade: Modalidade,
    itens: list[tuple[dict, Equipe | None]],
    pontuacao: PontuacaoModalidade | None,
) -> list[list[str]]:
    individual = modalidade.tipo_disputa == TipoDisputa.INDIVIDUAL
    rodadas = pontuacao.rodadas if pontuacao and individual else []
    if rodadas:
        cabecalho = ["Posicao", "Equipe", *[f"Rodada {n}" for _, n in rodadas], "Nota final"]
    elif pontuacao and not individual:
        cabecalho = ["Posicao", "Equipe", "Resultado", "Pontos marcados"]
    else:
        cabecalho = ["Posicao", "Equipe", "Resultado"]

    linhas = [cabecalho]
    for item, equipe in itens:
        linha = [str(item.get("posicao", "-")), equipe.nome if equipe else "-"]
        if rodadas:
            for rodada_id, _ in rodadas:
                nota = pontuacao.nota_por_rodada.get((item["equipe_id"], rodada_id))
                linha.append(_formatar_pontos(nota) if nota is not None else "-")
            linha.append(_formatar_pontos(item["nota_final"]))
        else:
            linha.append(_formatar_metrica_classificacao(modalidade, item))
            if pontuacao and not individual:
                linha.append(
                    _formatar_pontos(
                        pontuacao.pontos_por_equipe.get(item["equipe_id"], Decimal("0"))
                    )
                )
        linhas.append(linha)
    return linhas


def _tabela(linhas: list[list[str]]) -> Table:
    tabela = Table(linhas, hAlign="LEFT", repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return tabela


def _cabecalho_modalidade(estilos: StyleSheet1, modalidade: Modalidade) -> Paragraph:
    return Paragraph(
        f"Modalidade: {modalidade.nome} &nbsp;&nbsp; Tipo: {modalidade.tipo_disputa.value}"
        + (f" ({modalidade.formato_chaveamento.value})" if modalidade.formato_chaveamento else ""),
        estilos["Heading1"],
    )


async def gerar_relatorio_auditoria_pdf(db: AsyncSession, modalidade_id: UUID) -> bytes:
    """Monta um PDF de auditoria pra uma modalidade: todas as equipes
    inscritas com a posicao no ranking (mesma classificacao que o painel usa,
    via consolidacao.calcular_classificacao) - pra conferencia manual em caso
    de contestacao de equipe.
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    evento = await db.get(Evento, modalidade.evento_id)

    dados = await _carregar_dados_modalidade(db, modalidade)
    pontuacao = await _carregar_pontuacao(db, modalidade)

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = []

    gerado_em = _calcular_gerado_em() if evento else None
    elementos.append(Paragraph("Relatorio de auditoria", estilos["Title"]))
    elementos.append(
        Paragraph(
            f"Evento: {evento.nome if evento else '-'} &nbsp;&nbsp; "
            f"Modalidade: {modalidade.nome} &nbsp;&nbsp; "
            f"Tipo: {modalidade.tipo_disputa.value}"
            + (
                f" ({modalidade.formato_chaveamento.value})"
                if modalidade.formato_chaveamento
                else ""
            ),
            estilos["Normal"],
        )
    )
    if gerado_em:
        elementos.append(
            Paragraph(f"Gerado em: {gerado_em.strftime('%d/%m/%Y %H:%M')}", estilos["Normal"])
        )
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.extend(_montar_secao_modalidade(estilos, modalidade, *dados, pontuacao))

    documento.build(elementos)
    return buffer.getvalue()


async def gerar_relatorio_auditoria_evento_pdf(db: AsyncSession, evento_id: UUID) -> bytes:
    """Monta um unico PDF de auditoria com todas as modalidades do evento,
    cada uma em sua propria secao (separadas por quebra de pagina) - versao
    consolidada de gerar_relatorio_auditoria_pdf, pra nao precisar baixar um
    PDF por modalidade.
    """
    evento = await obter_evento(db, evento_id)

    resultado = await db.execute(
        select(Modalidade).where(Modalidade.evento_id == evento_id).order_by(Modalidade.nome)
    )
    modalidades = list(resultado.scalars().all())

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = []

    gerado_em = _calcular_gerado_em()
    elementos.append(Paragraph("Relatorio de auditoria geral", estilos["Title"]))
    elementos.append(Paragraph(f"Evento: {evento.nome}", estilos["Normal"]))
    elementos.append(
        Paragraph(f"Gerado em: {gerado_em.strftime('%d/%m/%Y %H:%M')}", estilos["Normal"])
    )
    elementos.append(Spacer(1, 0.5 * cm))

    if not modalidades:
        elementos.append(
            Paragraph("Nenhuma modalidade cadastrada neste evento.", estilos["Normal"])
        )

    for indice, modalidade in enumerate(modalidades):
        if indice > 0:
            elementos.append(PageBreak())
        elementos.append(_cabecalho_modalidade(estilos, modalidade))
        elementos.append(Spacer(1, 0.3 * cm))
        dados = await _carregar_dados_modalidade(db, modalidade)
        pontuacao = await _carregar_pontuacao(db, modalidade)
        elementos.extend(_montar_secao_modalidade(estilos, modalidade, *dados, pontuacao))

    documento.build(elementos)
    return buffer.getvalue()
