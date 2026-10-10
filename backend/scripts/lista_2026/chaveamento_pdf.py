"""
Script avulso: gera um PDF de chaveamento pra projetar num telao, uma pagina
por combinacao modalidade + nivel (fase de grupos e/ou mata-mata, conforme o
que existir). Nao faz parte do app -- e so uma foto do banco no momento em
que roda.

Mesma logica de nomeacao de fase que o front usa em
frontend/src/lib/fase-chaveamento.ts (calcularTotalRodadasPorNivel):
- Uma partida so entra na contagem de "inicio do mata-mata" se
  formato_chaveamento == MATA_MATA -- fase de grupos (TODOS_CONTRA_TODOS)
  nunca vira "Semifinal"/"Final" mesmo que tenha 2 ou 4 times por chave.
  (O PDF gerado numa sessao anterior tinha exatamente esse bug: rotulava
  rodada de todos-contra-todos como "Mata-mata - Semifinal/Final".)

Uso:
    docker compose exec -T api python3 -m scripts.lista_2026.chaveamento_pdf \
        /tmp/chaveamento.pdf
"""

import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.chave import Chave, ChaveEquipe
from app.models.equipe import Equipe
from app.models.modalidade import Modalidade, TipoDisputa
from app.models.partida import Partida
from app.models.rodada import Rodada

_FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")

_NOMES_FASE = ["Final", "Semifinal", "Quartas de Final", "Oitavas de Final"]
_COR_FASE = {
    "Final": colors.HexColor("#92400e"),
    "Semifinal": colors.HexColor("#0369a1"),
    "Quartas de Final": colors.HexColor("#334155"),
    "Oitavas de Final": colors.HexColor("#334155"),
}


def _rotulo_nivel(nivel: int) -> str:
    return "ABSOLUTO" if nivel == 1 else f"Nível {nivel}"


def _nome_fase(numero: int, total_rodadas: int | None) -> str | None:
    if not total_rodadas or total_rodadas <= 0:
        return None
    distancia = total_rodadas - numero
    if distancia < 0 or distancia >= len(_NOMES_FASE):
        return None
    return _NOMES_FASE[distancia]


class _PartidaDTO:
    def __init__(self, partida: Partida, numero_rodada: int, nome_a: str, nome_b: str | None):
        self.nivel = partida.nivel
        self.numero_rodada = numero_rodada
        self.chave_id = partida.chave_id
        self.formato = partida.formato_chaveamento
        self.status = partida.status
        self.nome_a = nome_a
        self.nome_b = nome_b
        self.equipe_a_id = partida.equipe_a_id
        self.equipe_b_id = partida.equipe_b_id
        self.vencedor_id = partida.vencedor_id


def _totais_mata_mata_por_nivel(partidas: list[_PartidaDTO]) -> dict[int, int]:
    """Espelha frontend/src/lib/fase-chaveamento.ts::calcularTotalRodadasPorNivel."""
    inicio_por_nivel: dict[int, int] = {}
    for p in partidas:
        if p.nivel is None or p.formato != "MATA_MATA":
            continue
        atual = inicio_por_nivel.get(p.nivel)
        if atual is None or p.numero_rodada < atual:
            inicio_por_nivel[p.nivel] = p.numero_rodada

    equipes_por_nivel: dict[int, set] = defaultdict(set)
    for p in partidas:
        if p.nivel is None or p.numero_rodada != inicio_por_nivel.get(p.nivel):
            continue
        equipes_por_nivel[p.nivel].add(p.equipe_a_id)
        if p.equipe_b_id:
            equipes_por_nivel[p.nivel].add(p.equipe_b_id)

    return {
        nivel: math.ceil(math.log2(len(equipes)))
        for nivel, equipes in equipes_por_nivel.items()
        if len(equipes) > 1
    }


async def _carregar_dados(db: AsyncSession) -> list[dict]:
    modalidades = list(
        (
            await db.scalars(
                select(Modalidade)
                .where(Modalidade.tipo_disputa == TipoDisputa.CONFRONTO)
                .order_by(Modalidade.nome)
            )
        ).all()
    )

    equipes = {e.id: e.nome for e in (await db.scalars(select(Equipe))).all()}
    chaves = {c.id: c for c in (await db.scalars(select(Chave))).all()}

    membros_por_chave: dict[UUID, list[str]] = defaultdict(list)
    resultado_membros = await db.execute(
        select(ChaveEquipe.chave_id, ChaveEquipe.equipe_id).order_by(ChaveEquipe.criado_em)
    )
    for chave_id, equipe_id in resultado_membros.all():
        membros_por_chave[chave_id].append(equipes.get(equipe_id, "?"))

    saida = []
    for modalidade in modalidades:
        resultado = await db.execute(
            select(Partida, Rodada.numero)
            .join(Rodada, Rodada.id == Partida.rodada_id)
            .where(Rodada.modalidade_id == modalidade.id)
            .order_by(Rodada.numero, Partida.nivel)
        )
        linhas = resultado.all()
        if not linhas:
            continue

        partidas_dto = [
            _PartidaDTO(
                p,
                numero_rodada,
                equipes.get(p.equipe_a_id, "?"),
                equipes.get(p.equipe_b_id) if p.equipe_b_id else None,
            )
            for p, numero_rodada in linhas
        ]
        totais_mata_mata = _totais_mata_mata_por_nivel(partidas_dto)

        niveis = sorted({p.nivel for p in partidas_dto if p.nivel is not None})
        for nivel in niveis:
            partidas_nivel = [p for p in partidas_dto if p.nivel == nivel]

            com_chave: dict[UUID, list[_PartidaDTO]] = defaultdict(list)
            sem_chave: list[_PartidaDTO] = []
            for p in partidas_nivel:
                if p.chave_id is not None:
                    com_chave[p.chave_id].append(p)
                else:
                    sem_chave.append(p)

            grupos = []
            for chave_id, partidas_chave in com_chave.items():
                chave = chaves.get(chave_id)
                grupos.append(
                    {
                        "nome": chave.nome if chave else "?",
                        "membros": membros_por_chave.get(chave_id, []),
                        "partidas": partidas_chave,
                    }
                )
            grupos.sort(key=lambda g: g["nome"])

            saida.append(
                {
                    "modalidade": modalidade.nome,
                    "nivel": nivel,
                    "grupos": grupos,
                    "sem_chave": sem_chave,
                    "total_rodadas_mata_mata": totais_mata_mata.get(nivel),
                }
            )

    return saida


def _linha_partida(p: _PartidaDTO) -> str:
    if p.nome_b is None:
        return f"{p.nome_a}  —  <i>(bye, avança direto)</i>"
    if p.status == "EMPATADA":
        return f"{p.nome_a}  x  {p.nome_b}  —  <i>empate</i>"
    if p.status == "ENCERRADA" and p.vencedor_id:
        vencedor = p.nome_a if p.vencedor_id == p.equipe_a_id else p.nome_b
        return f"{p.nome_a}  x  {p.nome_b}  —  <b>vencedor: {vencedor}</b>"
    return f"{p.nome_a}  x  {p.nome_b}"


def _tabela_partidas(linhas: list[str], estilos, largura: float) -> Table:
    dados = [[Paragraph(linha, estilos["Partida"])] for linha in linhas]
    tabela = Table(dados, colWidths=[largura])
    tabela.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return tabela


class _MarcaSecao(Flowable):
    """Flowable invisivel que atualiza o estado compartilhado com o
    titulo da secao atual (modalidade + nivel) -- lido pelo callback
    `_cabecalho_rodape` sempre que uma pagina e finalizada. Assim o
    cabecalho aparece em TODA pagina fisica da secao, mesmo quando o
    conteudo (ex.: fase de grupos com muitas chaves) estoura pra 2+
    paginas -- sem isso, so a 1a pagina de cada secao mostrava o titulo,
    e quem manuseia o telao perdia o contexto nas paginas seguintes.
    """

    def __init__(self, estado: dict, modalidade: str, nivel: str):
        super().__init__()
        self.estado = estado
        self.modalidade = modalidade
        self.nivel = nivel
        self.width = 0
        self.height = 0

    def wrap(self, avail_width, avail_height):
        self.estado["modalidade"] = self.modalidade
        self.estado["nivel"] = self.nivel
        return (0, 0)

    def draw(self):
        pass


def _cabecalho_rodape(estado: dict, gerado_em_texto: str):
    def desenhar(canvas, doc):
        canvas.saveState()
        largura_pagina, altura_pagina = doc.pagesize
        centro_x = largura_pagina / 2

        canvas.setFillColor(colors.HexColor("#0f172a"))
        canvas.setFont("Helvetica-Bold", 30)
        canvas.drawCentredString(centro_x, altura_pagina - 1.8 * cm, estado.get("modalidade", ""))

        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawCentredString(centro_x, altura_pagina - 2.55 * cm, estado.get("nivel", ""))

        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            largura_pagina - 1.5 * cm, 1 * cm, f"Gerado em {gerado_em_texto} · pág. {doc.page}"
        )
        canvas.restoreState()

    return desenhar


def _montar_pagina(secao: dict, estilos, largura_util: float) -> list:
    elementos = []

    if secao["grupos"]:
        elementos.append(Paragraph("Fase de grupos", estilos["Secao"]))
        for grupo in secao["grupos"]:
            bloco = [
                Paragraph(f"{grupo['nome']}: {', '.join(grupo['membros'])}", estilos["NomeChave"]),
            ]
            por_rodada: dict[int, list[_PartidaDTO]] = defaultdict(list)
            for p in grupo["partidas"]:
                por_rodada[p.numero_rodada].append(p)
            for numero in sorted(por_rodada):
                linhas = [_linha_partida(p) for p in por_rodada[numero]]
                bloco.append(Paragraph(f"Rodada {numero}", estilos["RotuloRodada"]))
                bloco.append(_tabela_partidas(linhas, estilos, largura_util))
            bloco.append(Spacer(1, 0.35 * cm))
            elementos.append(KeepTogether(bloco))
        if not secao["sem_chave"]:
            elementos.append(
                Paragraph(
                    "Mata-mata entre os classificados: a ser montado pelo coordenador.",
                    estilos["Aviso"],
                )
            )

    if secao["sem_chave"]:
        mata_mata = [p for p in secao["sem_chave"] if p.formato == "MATA_MATA"]
        robin = [p for p in secao["sem_chave"] if p.formato != "MATA_MATA"]

        if robin:
            elementos.append(Paragraph("Todos contra todos", estilos["Secao"]))
            por_rodada = defaultdict(list)
            for p in robin:
                por_rodada[p.numero_rodada].append(p)
            for numero in sorted(por_rodada):
                linhas = [_linha_partida(p) for p in por_rodada[numero]]
                elementos.append(Paragraph(f"Rodada {numero}", estilos["RotuloRodada"]))
                elementos.append(_tabela_partidas(linhas, estilos, largura_util))

        if mata_mata:
            elementos.append(Paragraph("Mata-mata", estilos["Secao"]))
            total = secao["total_rodadas_mata_mata"]
            por_rodada = defaultdict(list)
            for p in mata_mata:
                por_rodada[p.numero_rodada].append(p)
            for numero in sorted(por_rodada):
                fase = _nome_fase(numero, total)
                rotulo = fase if fase else f"Rodada {numero}"
                cor = _COR_FASE.get(fase, colors.HexColor("#334155"))
                estilo_fase = ParagraphStyle("Fase", parent=estilos["RotuloRodada"], textColor=cor)
                linhas = [_linha_partida(p) for p in por_rodada[numero]]
                elementos.append(Paragraph(rotulo, estilo_fase))
                elementos.append(_tabela_partidas(linhas, estilos, largura_util))

    return elementos


def _estilos():
    base = getSampleStyleSheet()
    base.add(
        ParagraphStyle(
            "Secao",
            fontSize=15,
            leading=18,
            fontName="Helvetica-Bold",
            textColor=colors.white,
            backColor=colors.HexColor("#1e293b"),
            spaceBefore=10,
            spaceAfter=8,
            leftIndent=6,
            borderPadding=6,
        )
    )
    base.add(
        ParagraphStyle(
            "NomeChave",
            fontSize=13,
            leading=16,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    base.add(
        ParagraphStyle(
            "RotuloRodada",
            fontSize=11,
            leading=14,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#334155"),
            spaceBefore=4,
            spaceAfter=2,
            leftIndent=10,
        )
    )
    base.add(
        ParagraphStyle(
            "Partida",
            fontSize=13,
            leading=17,
            fontName="Helvetica",
            textColor=colors.HexColor("#0f172a"),
        )
    )
    base.add(
        ParagraphStyle(
            "Aviso",
            fontSize=11,
            leading=14,
            fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#92400e"),
            spaceBefore=6,
        )
    )
    return base


async def gerar(caminho_saida: str) -> None:
    async with AsyncSessionLocal() as db:
        secoes = await _carregar_dados(db)

    estilos = _estilos()
    gerado_em = datetime.now(UTC).astimezone(_FUSO_FORTALEZA)
    gerado_em_texto = gerado_em.strftime("%d/%m/%Y %H:%M")
    pagesize = landscape(A4)
    margem_lateral = 1.5 * cm
    margem_topo = 3.4 * cm  # reserva espaco pro cabecalho repetido (ver _cabecalho_rodape)
    margem_base = 1.5 * cm
    largura_util = pagesize[0] - 2 * margem_lateral

    estado_secao_atual: dict = {"modalidade": "", "nivel": ""}

    frame = Frame(
        margem_lateral,
        margem_base,
        pagesize[0] - 2 * margem_lateral,
        pagesize[1] - margem_topo - margem_base,
        id="conteudo",
    )
    documento = BaseDocTemplate(
        caminho_saida,
        pagesize=pagesize,
        title="Chaveamento — TJR 2026",
    )
    documento.addPageTemplates(
        [
            PageTemplate(
                id="secao",
                frames=[frame],
                onPage=_cabecalho_rodape(estado_secao_atual, gerado_em_texto),
            )
        ]
    )

    if secoes:
        estado_secao_atual["modalidade"] = secoes[0]["modalidade"]
        estado_secao_atual["nivel"] = _rotulo_nivel(secoes[0]["nivel"])

    elementos = []
    for i, secao in enumerate(secoes):
        if i > 0:
            # A marca tem que rodar (wrap()) ANTES do PageBreak, na pagina que
            # esta terminando -- assim, quando o onPage da proxima pagina
            # dispara (no INICIO dela, antes de qualquer flowable dessa
            # pagina ser desenhado), o estado ja reflete a secao nova. Sem
            # isso a 1a pagina de cada secao (inclusive a pagina 1 do PDF
            # inteiro, tratada acima) ficava sem cabecalho nenhum.
            elementos.append(
                _MarcaSecao(estado_secao_atual, secao["modalidade"], _rotulo_nivel(secao["nivel"]))
            )
            elementos.append(PageBreak())
        elementos.extend(_montar_pagina(secao, estilos, largura_util))

    documento.build(elementos)
    print(f"{len(secoes)} secao(oes) de chaveamento escritas em {caminho_saida}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 -m scripts.lista_2026.chaveamento_pdf <caminho-saida.pdf>")
        sys.exit(1)
    import asyncio

    asyncio.run(gerar(sys.argv[1]))
