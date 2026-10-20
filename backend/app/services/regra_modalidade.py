"""PDFs de regras por modalidade: o manual completo e o caderninho do aluno.

O coordenador envia pelo Painel; qualquer pessoa (sem login) le pela tela
inicial. Enviar de novo troca o arquivo, sem guardar versao antiga: regra nao e
dado de pontuacao.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.modalidade import Modalidade
from app.models.regra_modalidade import RegraModalidade, TipoRegra
from app.services.modalidade import obter_modalidade

TAMANHO_MAXIMO_BYTES = 30 * 1024 * 1024


@dataclass
class RegraResumo:
    tipo: TipoRegra
    nome_arquivo: str
    atualizado_em: datetime


@dataclass
class ModalidadeComRegras:
    id: UUID
    nome: str
    regras: list[RegraResumo] = field(default_factory=list)


async def _buscar(db: AsyncSession, modalidade_id: UUID, tipo: TipoRegra) -> RegraModalidade | None:
    return await db.scalar(
        select(RegraModalidade).where(
            RegraModalidade.modalidade_id == modalidade_id, RegraModalidade.tipo == tipo
        )
    )


async def enviar_regra(
    db: AsyncSession,
    modalidade_id: UUID,
    tipo: TipoRegra,
    *,
    nome_arquivo: str,
    conteudo: bytes,
    usuario_id: UUID,
) -> RegraModalidade:
    await obter_modalidade(db, modalidade_id)
    if not conteudo.startswith(b"%PDF"):
        raise AppError(
            codigo="ARQUIVO_NAO_E_PDF",
            mensagem="O arquivo precisa ser um PDF.",
            status_code=422,
        )
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        raise AppError(
            codigo="ARQUIVO_GRANDE_DEMAIS",
            mensagem=f"O PDF passa de {TAMANHO_MAXIMO_BYTES // (1024 * 1024)} MB.",
            status_code=422,
        )

    regra = await _buscar(db, modalidade_id, tipo)
    if regra is None:
        regra = RegraModalidade(modalidade_id=modalidade_id, tipo=tipo)
        db.add(regra)
    regra.nome_arquivo = nome_arquivo[:255]
    regra.conteudo = conteudo
    regra.enviado_por_id = usuario_id
    await db.flush()
    await db.refresh(regra)
    return regra


async def obter_regra(db: AsyncSession, modalidade_id: UUID, tipo: TipoRegra) -> RegraModalidade:
    regra = await _buscar(db, modalidade_id, tipo)
    if regra is None:
        raise AppError(
            codigo="REGRA_NAO_ENCONTRADA",
            mensagem="Esse PDF ainda nao foi enviado.",
            status_code=404,
        )
    return regra


async def remover_regra(db: AsyncSession, modalidade_id: UUID, tipo: TipoRegra) -> None:
    await db.delete(await obter_regra(db, modalidade_id, tipo))
    await db.flush()


async def listar_regras_do_evento(db: AsyncSession, evento_id: UUID) -> list[ModalidadeComRegras]:
    """Toda modalidade do evento, com os PDFs que ja tem. Nao carrega o conteudo."""
    modalidades = (
        await db.execute(
            select(Modalidade.id, Modalidade.nome)
            .where(Modalidade.evento_id == evento_id)
            .order_by(Modalidade.nome)
        )
    ).tuples()
    resultado = {mid: ModalidadeComRegras(id=mid, nome=nome) for mid, nome in modalidades}
    linhas = await db.execute(
        select(
            RegraModalidade.modalidade_id,
            RegraModalidade.tipo,
            RegraModalidade.nome_arquivo,
            RegraModalidade.atualizado_em,
        )
        .where(RegraModalidade.modalidade_id.in_(resultado))
        .order_by(RegraModalidade.tipo)
    )
    for modalidade_id, tipo, nome_arquivo, atualizado_em in linhas.tuples():
        resultado[modalidade_id].regras.append(RegraResumo(tipo, nome_arquivo, atualizado_em))
    return list(resultado.values())
