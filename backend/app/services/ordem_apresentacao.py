"""Sequencia de competicao (ordem de apresentacao) das equipes em modalidade INDIVIDUAL.

Substitui o agendamento por arena/horario: o coordenador sorteia (ou ajusta na
mao) a sequencia de cada nivel, e a mesma ordem vale pra todas as rodadas. Qual
arena a equipe usa e decidido na hora, no ginasio.
"""

import random
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.modalidade import Modalidade, TipoDisputa
from app.services.audit import registrar_audit_log
from app.services.modalidade import obter_modalidade


def _exigir_individual(modalidade: Modalidade) -> None:
    if modalidade.tipo_disputa != TipoDisputa.INDIVIDUAL:
        raise AppError(
            codigo="ORDEM_SO_INDIVIDUAL",
            mensagem="Sequencia de competicao so existe em modalidade individual.",
            status_code=422,
        )


async def _inscricoes_do_nivel(
    db: AsyncSession, modalidade_id: UUID, nivel: int
) -> list[Inscricao]:
    modalidade = await obter_modalidade(db, modalidade_id)
    _exigir_individual(modalidade)
    resultado = await db.scalars(
        select(Inscricao)
        .join(Equipe, Equipe.id == Inscricao.equipe_id)
        .where(
            Inscricao.modalidade_id == modalidade_id,
            Equipe.nivel == nivel,
            Equipe.ativo.is_(True),
        )
    )
    return list(resultado.all())


async def _gravar(
    db: AsyncSession,
    modalidade_id: UUID,
    nivel: int,
    inscricoes_em_ordem: list[Inscricao],
    *,
    acao: str,
    usuario_id: UUID,
) -> None:
    antes = {str(i.equipe_id): i.ordem_apresentacao for i in inscricoes_em_ordem}
    for posicao, inscricao in enumerate(inscricoes_em_ordem, start=1):
        inscricao.ordem_apresentacao = posicao
    await db.flush()
    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="modalidade",
        entidade_id=modalidade_id,
        acao=acao,
        antes={"nivel": nivel, "ordem": antes},
        depois={"nivel": nivel, "ordem": [str(i.equipe_id) for i in inscricoes_em_ordem]},
    )


async def sortear_ordem(
    db: AsyncSession, modalidade_id: UUID, *, nivel: int, usuario_id: UUID
) -> None:
    inscricoes = await _inscricoes_do_nivel(db, modalidade_id, nivel)
    random.shuffle(inscricoes)
    await _gravar(db, modalidade_id, nivel, inscricoes, acao="SORTEAR_ORDEM", usuario_id=usuario_id)


async def definir_ordem(
    db: AsyncSession,
    modalidade_id: UUID,
    *,
    nivel: int,
    equipe_ids: list[UUID],
    usuario_id: UUID,
) -> None:
    inscricoes = await _inscricoes_do_nivel(db, modalidade_id, nivel)
    por_equipe = {i.equipe_id: i for i in inscricoes}
    if len(equipe_ids) != len(set(equipe_ids)) or set(equipe_ids) != set(por_equipe):
        raise AppError(
            codigo="ORDEM_INCOMPLETA",
            mensagem=(
                "A ordem precisa conter cada equipe inscrita neste nivel exatamente uma vez."
            ),
            status_code=422,
        )
    await _gravar(
        db,
        modalidade_id,
        nivel,
        [por_equipe[equipe_id] for equipe_id in equipe_ids],
        acao="DEFINIR_ORDEM",
        usuario_id=usuario_id,
    )


@dataclass
class EquipeNaSequencia:
    nome: str
    presente: bool


@dataclass
class SequenciaNivel:
    nivel: int
    sorteada: bool
    equipes: list[EquipeNaSequencia]


async def listar_sequencia(db: AsyncSession, modalidade_id: UUID) -> list[SequenciaNivel]:
    """Sequencia de competicao de cada nivel, na ordem que a tela de pontuar
    usa: ordem sorteada/ajustada e, sem ordem, alfabetica. Equipe desativada
    fica de fora; ausente aparece marcada (pode chegar atrasada)."""
    modalidade = await obter_modalidade(db, modalidade_id)
    _exigir_individual(modalidade)
    linhas = (
        await db.execute(
            select(Equipe, Inscricao)
            .join(Inscricao, Inscricao.equipe_id == Equipe.id)
            .where(Inscricao.modalidade_id == modalidade_id, Equipe.ativo.is_(True))
        )
    ).tuples()

    por_nivel: dict[int, list[tuple[Equipe, Inscricao]]] = {}
    for equipe, inscricao in linhas:
        por_nivel.setdefault(equipe.nivel, []).append((equipe, inscricao))

    sequencia = []
    for nivel in sorted(por_nivel):
        itens = sorted(
            por_nivel[nivel],
            key=lambda par: (
                par[1].ordem_apresentacao is None,
                par[1].ordem_apresentacao or 0,
                par[0].nome.lower(),
            ),
        )
        sequencia.append(
            SequenciaNivel(
                nivel=nivel,
                sorteada=any(inscricao.ordem_apresentacao is not None for _, inscricao in itens),
                equipes=[EquipeNaSequencia(nome=e.nome, presente=e.presente) for e, _ in itens],
            )
        )
    return sequencia


def _rotulo_nivel(nivel: int) -> str:
    # Mesmo rotulo do front (lib/nivel.ts): nivel 1 e exibido como ABSOLUTO.
    return "ABSOLUTO" if nivel == 1 else f"Nível {nivel}"


async def gerar_sequencia_pdf(db: AsyncSession, modalidade_id: UUID) -> bytes:
    """PDF pra projetar no telao: paisagem, letra grande, uma pagina por nivel."""
    modalidade = await obter_modalidade(db, modalidade_id)
    sequencia = await listar_sequencia(db, modalidade_id)

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f"Sequência de competição - {modalidade.nome}",
    )
    titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=34, leading=40)
    subtitulo = ParagraphStyle(
        "subtitulo", fontName="Helvetica", fontSize=18, leading=22, textColor=colors.grey
    )

    elementos: list = []
    if not sequencia:
        elementos += [
            Paragraph(escape(modalidade.nome), titulo),
            Paragraph("Nenhuma equipe inscrita ainda.", subtitulo),
        ]
    for indice, nivel in enumerate(sequencia):
        if indice > 0:
            elementos.append(PageBreak())
        elementos += [
            Paragraph(f"{escape(modalidade.nome)} · {_rotulo_nivel(nivel.nivel)}", titulo),
            Paragraph("Sequência de competição", subtitulo),
            Spacer(1, 0.6 * cm),
        ]
        # Fonte encolhe com nivel grande pra caber mais linha por pagina;
        # se ainda nao couber, a tabela continua na pagina seguinte.
        tamanho = 26 if len(nivel.equipes) <= 10 else 20 if len(nivel.equipes) <= 16 else 16
        celula = ParagraphStyle(
            "celula", fontName="Helvetica", fontSize=tamanho, leading=tamanho * 1.2
        )
        numero = ParagraphStyle("numero", parent=celula, fontName="Helvetica-Bold", alignment=2)
        linhas = [
            [
                Paragraph(f"{posicao}º", numero),
                Paragraph(
                    escape(equipe.nome) + ("" if equipe.presente else "  <i>(ausente)</i>"),
                    celula,
                ),
            ]
            for posicao, equipe in enumerate(nivel.equipes, start=1)
        ]
        tabela = Table(linhas, colWidths=[3 * cm, None], repeatRows=0)
        tabela.setStyle(
            TableStyle(
                [
                    (
                        "ROWBACKGROUNDS",
                        (0, 0),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f1f5f9")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elementos.append(tabela)
        if not nivel.sorteada:
            elementos += [
                Spacer(1, 0.4 * cm),
                Paragraph("Ordem ainda não sorteada (lista em ordem alfabética).", subtitulo),
            ]

    documento.build(elementos)
    return buffer.getvalue()
