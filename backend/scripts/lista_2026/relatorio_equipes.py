"""
Script avulso: gera um PDF com a relacao de equipes cadastradas no banco,
como estao agora (nome, nivel, modalidades em que cada uma esta inscrita).
Nao faz parte do app -- e so uma foto do banco no momento em que roda.

Uso:
    docker compose exec -T api python3 -m scripts.lista_2026.relatorio_equipes \
        /tmp/relacao_equipes.pdf
"""

import sys
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.modalidade import Modalidade

_FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")


def _rotulo_nivel(nivel: int) -> str:
    return "ABSOLUTO" if nivel == 1 else f"Nível {nivel}"


async def _carregar_dados(db: AsyncSession) -> list[dict]:
    equipes = list((await db.scalars(select(Equipe).order_by(Equipe.nome))).all())

    resultado = await db.execute(
        select(Inscricao.equipe_id, Modalidade.nome).join(
            Modalidade, Inscricao.modalidade_id == Modalidade.id
        )
    )
    modalidades_por_equipe: dict = {}
    for equipe_id, nome_modalidade in resultado.all():
        modalidades_por_equipe.setdefault(equipe_id, []).append(nome_modalidade)

    linhas = []
    for equipe in equipes:
        modalidades = sorted(modalidades_por_equipe.get(equipe.id, []))
        linhas.append(
            {
                "nome": equipe.nome,
                "nivel": _rotulo_nivel(equipe.nivel),
                "modalidades": ", ".join(modalidades) if modalidades else "(nenhuma)",
                "ativo": equipe.ativo,
            }
        )
    return linhas


async def gerar(caminho_saida: str) -> None:
    async with AsyncSessionLocal() as db:
        linhas = await _carregar_dados(db)

    estilos = getSampleStyleSheet()
    gerado_em = datetime.now(UTC).astimezone(_FUSO_FORTALEZA)

    documento = SimpleDocTemplate(
        caminho_saida,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    elementos = [
        Paragraph("Relação de equipes — TJR 2026", estilos["Title"]),
        Paragraph(
            f"Gerado em: {gerado_em.strftime('%d/%m/%Y %H:%M')} · Total: {len(linhas)} equipe(s)",
            estilos["Normal"],
        ),
        Spacer(1, 0.5 * cm),
    ]

    cabecalho = ["Equipe", "Nível", "Modalidades", "Status"]
    dados_tabela = [cabecalho]
    for linha in linhas:
        dados_tabela.append(
            [
                Paragraph(linha["nome"], estilos["Normal"]),
                linha["nivel"],
                Paragraph(linha["modalidades"], estilos["Normal"]),
                "Ativa" if linha["ativo"] else "Inativa",
            ]
        )

    tabela = Table(dados_tabela, colWidths=[5 * cm, 2.3 * cm, 8 * cm, 1.7 * cm], repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elementos.append(tabela)

    documento.build(elementos)
    print(f"{len(linhas)} equipe(s) escritas em {caminho_saida}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 -m scripts.lista_2026.relatorio_equipes <caminho-saida.pdf>")
        sys.exit(1)
    import asyncio

    asyncio.run(gerar(sys.argv[1]))
