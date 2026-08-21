from datetime import UTC
from io import BytesIO
from uuid import UUID
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.lancamento import Lancamento
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import FormatoChaveamento, Modalidade, TipoDisputa
from app.models.rodada import Rodada
from app.models.usuario import Usuario
from app.services.consolidacao import calcular_classificacao
from app.services.modalidade import obter_modalidade

_FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")


def _formatar_metrica_classificacao(modalidade: Modalidade, item: dict) -> str:
    """Mesma logica de exibicao do RankingOut (ranking.py): o formato do
    numero depende de tipo_disputa/formato_chaveamento, nao do conteudo do
    dict - calcular_classificacao sempre devolve as mesmas chaves pras 3
    variantes, so o que faz sentido mostrar muda.
    """
    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        if modalidade.formato_chaveamento == FormatoChaveamento.MATA_MATA:
            return f"{item['vitorias']}V {item['derrotas']}D"
        if modalidade.formato_chaveamento == FormatoChaveamento.TODOS_CONTRA_TODOS:
            return (
                f"{item['nota_final']} pts "
                f"({item['vitorias']}V {item['empates']}E {item['derrotas']}D)"
            )
    return str(item["nota_final"])


async def gerar_relatorio_auditoria_pdf(db: AsyncSession, modalidade_id: UUID) -> bytes:
    """Monta um PDF de auditoria pra uma modalidade: todas as equipes
    inscritas com a posicao no ranking (mesma classificacao que o painel usa,
    via consolidacao.calcular_classificacao), e todos os lancamentos feitos
    (rodada, tentativa, itens, pontos, status, arbitro) - pra conferencia
    manual em caso de contestacao de equipe.
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    evento = await db.get(Evento, modalidade.evento_id)

    classificacao = await calcular_classificacao(db, modalidade_id)
    equipe_ids = {item["equipe_id"] for item in classificacao}

    resultado = await db.execute(
        select(Lancamento, Rodada, Equipe, Usuario)
        .join(Rodada, Lancamento.rodada_id == Rodada.id)
        .join(Equipe, Lancamento.equipe_id == Equipe.id)
        .join(Usuario, Lancamento.arbitro_id == Usuario.id)
        .where(Rodada.modalidade_id == modalidade_id)
        .order_by(Rodada.numero, Equipe.nome, Lancamento.tentativa)
    )
    linhas_lancamento = resultado.all()
    equipe_ids.update(equipe.id for _, _, equipe, _ in linhas_lancamento)

    equipes_por_id: dict[UUID, Equipe] = {}
    if equipe_ids:
        resultado_equipes = await db.execute(select(Equipe).where(Equipe.id.in_(equipe_ids)))
        equipes_por_id = {e.id: e for e in resultado_equipes.scalars().all()}

    lancamento_ids = [lanc.id for lanc, _, _, _ in linhas_lancamento]
    itens_por_lancamento: dict[UUID, list[LancamentoItem]] = {}
    if lancamento_ids:
        resultado_itens = await db.execute(
            select(LancamentoItem)
            .where(LancamentoItem.lancamento_id.in_(lancamento_ids))
            .order_by(LancamentoItem.criado_em)
        )
        for item in resultado_itens.scalars().all():
            itens_por_lancamento.setdefault(item.lancamento_id, []).append(item)

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

    gerado_em = evento.criado_em.astimezone(UTC).astimezone(_FUSO_FORTALEZA) if evento else None
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

    elementos.append(Paragraph("Classificacao", estilos["Heading2"]))
    linhas_classificacao = [["Posicao", "Equipe", "Nivel", "Resultado"]]
    for item in classificacao:
        equipe = equipes_por_id.get(item["equipe_id"])
        linhas_classificacao.append(
            [
                str(item.get("posicao", "-")),
                equipe.nome if equipe else "-",
                str(equipe.nivel) if equipe else "-",
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
    elementos.append(Spacer(1, 0.7 * cm))

    elementos.append(Paragraph("Lancamentos", estilos["Heading2"]))
    if not linhas_lancamento:
        elementos.append(
            Paragraph("Nenhum lancamento registrado nesta modalidade.", estilos["Normal"])
        )
    for lancamento, rodada, equipe, arbitro in linhas_lancamento:
        elementos.append(
            Paragraph(
                f"Rodada {rodada.numero} - Tentativa {lancamento.tentativa} - {equipe.nome} "
                f"- {lancamento.status.value} - Total: {lancamento.total} "
                f"- Arbitro: {arbitro.nome}",
                estilos["Normal"],
            )
        )
        itens = itens_por_lancamento.get(lancamento.id, [])
        if itens:
            linhas_itens = [["Criterio", "Ocorrencias/Valor", "Pontos"]]
            for item in itens:
                nome_criterio = item.criterio_snapshot.get("nome", "-")
                ocorrencia = item.ocorrencias if item.ocorrencias is not None else item.valor
                linhas_itens.append([nome_criterio, str(ocorrencia), str(item.pontos)])
            tabela_itens = Table(linhas_itens, hAlign="LEFT")
            tabela_itens.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            elementos.append(tabela_itens)
        elementos.append(Spacer(1, 0.3 * cm))

    documento.build(elementos)
    return buffer.getvalue()
