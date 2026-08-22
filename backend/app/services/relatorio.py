from datetime import UTC
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
from app.models.lancamento import Lancamento
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import FormatoChaveamento, Modalidade, TipoDisputa
from app.models.rodada import Rodada
from app.models.usuario import Usuario
from app.services.consolidacao import calcular_classificacao
from app.services.evento import obter_evento
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


async def _carregar_dados_modalidade(
    db: AsyncSession, modalidade: Modalidade
) -> tuple[list[dict], list[tuple], dict[UUID, Equipe], dict[UUID, list[LancamentoItem]]]:
    """Busca a classificacao e todos os lancamentos (com itens) de uma
    modalidade - dado cru, sem nenhuma formatacao de PDF, reutilizado tanto
    pelo relatorio de uma unica modalidade quanto pelo relatorio geral do
    evento (uma chamada por modalidade).
    """
    classificacao = await calcular_classificacao(db, modalidade.id)
    equipe_ids = {item["equipe_id"] for item in classificacao}

    resultado = await db.execute(
        select(Lancamento, Rodada, Equipe, Usuario)
        .join(Rodada, Lancamento.rodada_id == Rodada.id)
        .join(Equipe, Lancamento.equipe_id == Equipe.id)
        .join(Usuario, Lancamento.arbitro_id == Usuario.id)
        .where(Rodada.modalidade_id == modalidade.id)
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

    return classificacao, linhas_lancamento, equipes_por_id, itens_por_lancamento


def agrupar_lancamentos_por_combate(
    linhas_lancamento: list[tuple],
) -> list[list[tuple]]:
    """Agrupa as linhas (Lancamento, Rodada, Equipe, Usuario) que pertencem
    ao mesmo combate (mesma partida_id + tentativa) - os dois lados de um
    confronto, uma linha por lado. Lancamento de modalidade INDIVIDUAL
    (partida_id None) fica sozinho no proprio grupo. Preserva a ordem de
    chegada tanto dos grupos quanto dos itens dentro de cada grupo.
    """
    grupos_por_chave: dict[tuple, list[tuple]] = {}
    resultado: list[list[tuple]] = []

    for linha in linhas_lancamento:
        lancamento = linha[0]
        if lancamento.partida_id is None:
            resultado.append([linha])
            continue

        chave = (lancamento.partida_id, lancamento.tentativa)
        grupo = grupos_por_chave.get(chave)
        if grupo is None:
            grupo = []
            grupos_por_chave[chave] = grupo
            resultado.append(grupo)
        grupo.append(linha)

    return resultado


def descrever_resultado_combate(nome_a: str, total_a: float, nome_b: str, total_b: float) -> str:
    """Descreve o resultado de um combate de forma explicita: placar dos dois
    lados e quem ganhou (ou empate) - usado no relatorio de auditoria pra
    deixar claro qual foi o confronto e quem ganhou/perdeu, sem precisar
    inferir comparando dois lancamentos separados na leitura.
    """
    if total_a > total_b:
        veredito = f"Vencedor: {nome_a}"
    elif total_b > total_a:
        veredito = f"Vencedor: {nome_b}"
    else:
        veredito = "Empate"
    return f"{nome_a} {total_a} x {total_b} {nome_b} — {veredito}"


def _montar_secao_modalidade(
    estilos: StyleSheet1,
    modalidade: Modalidade,
    classificacao: list[dict],
    linhas_lancamento: list[tuple],
    equipes_por_id: dict[UUID, Equipe],
    itens_por_lancamento: dict[UUID, list[LancamentoItem]],
) -> list:
    """Monta os flowables de classificacao + lancamentos de uma modalidade -
    o corpo do relatorio, sem cabecalho de documento. Reutilizado pelo
    relatorio de uma unica modalidade e pelo relatorio geral do evento (uma
    secao por modalidade, separadas por quebra de pagina).
    """
    elementos: list = []

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

    for grupo in agrupar_lancamentos_por_combate(linhas_lancamento):
        primeiro_lancamento, primeira_rodada, _primeira_equipe, _primeiro_arbitro = grupo[0]

        if primeiro_lancamento.partida_id is not None:
            if len(grupo) == 2:
                (_lanc_a, _, equipe_a, _), (_lanc_b, _, equipe_b, _) = grupo
                resultado = descrever_resultado_combate(
                    equipe_a.nome, grupo[0][0].total, equipe_b.nome, grupo[1][0].total
                )
            else:
                (_lanc_a, _, equipe_a, _) = grupo[0]
                resultado = f"{equipe_a.nome} x (aguardando equipe adversaria)"
            elementos.append(
                Paragraph(
                    f"<b>Confronto — Rodada {primeira_rodada.numero} · "
                    f"Tentativa {primeiro_lancamento.tentativa}:</b> {resultado}",
                    estilos["Normal"],
                )
            )

        for lancamento, rodada, equipe, arbitro in grupo:
            prefixo = (
                ""
                if lancamento.partida_id is not None
                else f"Rodada {rodada.numero} - Tentativa {lancamento.tentativa} - "
            )
            elementos.append(
                Paragraph(
                    f"{prefixo}{equipe.nome} - {lancamento.status.value} "
                    f"- Total: {lancamento.total} - Arbitro: {arbitro.nome}",
                    estilos["Normal"],
                )
            )
            tabela_itens = _tabela_itens(itens_por_lancamento.get(lancamento.id, []))
            if tabela_itens is not None:
                elementos.append(tabela_itens)
        elementos.append(Spacer(1, 0.3 * cm))

    return elementos


def _tabela_itens(itens: list[LancamentoItem]) -> Table | None:
    if not itens:
        return None
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
    return tabela_itens


def _cabecalho_modalidade(estilos: StyleSheet1, modalidade: Modalidade) -> Paragraph:
    return Paragraph(
        f"Modalidade: {modalidade.nome} &nbsp;&nbsp; Tipo: {modalidade.tipo_disputa.value}"
        + (f" ({modalidade.formato_chaveamento.value})" if modalidade.formato_chaveamento else ""),
        estilos["Heading1"],
    )


async def gerar_relatorio_auditoria_pdf(db: AsyncSession, modalidade_id: UUID) -> bytes:
    """Monta um PDF de auditoria pra uma modalidade: todas as equipes
    inscritas com a posicao no ranking (mesma classificacao que o painel usa,
    via consolidacao.calcular_classificacao), e todos os lancamentos feitos
    (rodada, tentativa, itens, pontos, status, arbitro) - pra conferencia
    manual em caso de contestacao de equipe.
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    evento = await db.get(Evento, modalidade.evento_id)

    dados = await _carregar_dados_modalidade(db, modalidade)
    classificacao, _linhas_lancamento, _equipes_por_id, _itens_por_lancamento = dados

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

    gerado_em = evento.criado_em.astimezone(UTC).astimezone(_FUSO_FORTALEZA)
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
