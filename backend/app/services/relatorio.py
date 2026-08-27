from datetime import UTC, datetime
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
from app.models.modalidade import FormatoChaveamento, Modalidade, TipoDisputa
from app.services.consolidacao import calcular_classificacao
from app.services.evento import obter_evento
from app.services.modalidade import obter_modalidade

_FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")


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
                f"Nivel {nivel}" if nivel is not None else "Nivel nao identificado",
                estilos["Heading3"],
            )
        )
        linhas_classificacao = [["Posicao", "Equipe", "Resultado"]]
        for item, equipe in grupos_por_nivel[nivel]:
            linhas_classificacao.append(
                [
                    str(item.get("posicao", "-")),
                    equipe.nome if equipe else "-",
                    _formatar_metrica_classificacao(modalidade, item),
                ]
            )
        tabela_classificacao = Table(linhas_classificacao, hAlign="LEFT")
        tabela_classificacao.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        elementos.append(tabela_classificacao)
        elementos.append(Spacer(1, 0.5 * cm))

    return elementos


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

    elementos.extend(_montar_secao_modalidade(estilos, modalidade, *dados))

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
        elementos.extend(_montar_secao_modalidade(estilos, modalidade, *dados))

    documento.build(elementos)
    return buffer.getvalue()
