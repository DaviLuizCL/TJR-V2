"""Pedido de conta feito pelo proprio juiz, aprovado pela coordenacao.

Sem e-mail de confirmacao: quem garante que a pessoa e juiz de verdade e o
coordenador, conferindo no grupo de juizes antes de aprovar. O pedido guarda
so o hash da senha; a conta (Usuario ARBITRO) so nasce na aprovacao.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_senha, verificar_senha
from app.models.solicitacao_acesso import SolicitacaoAcesso, SolicitacaoStatus
from app.models.usuario import Papel, Usuario
from app.schemas.solicitacao_acesso import SolicitacaoAcessoCreate
from app.services.audit import registrar_audit_log


async def _recusar_se_email_tem_conta(db: AsyncSession, email: str) -> None:
    if await db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
        raise AppError(
            codigo="EMAIL_JA_CADASTRADO",
            mensagem="Ja existe uma conta com este email.",
            status_code=409,
        )


async def _pendente_do_email(db: AsyncSession, email: str) -> SolicitacaoAcesso | None:
    return await db.scalar(
        select(SolicitacaoAcesso).where(
            SolicitacaoAcesso.email == email,
            SolicitacaoAcesso.status == SolicitacaoStatus.PENDENTE,
        )
    )


async def solicitar_acesso(db: AsyncSession, dto: SolicitacaoAcessoCreate) -> SolicitacaoAcesso:
    await _recusar_se_email_tem_conta(db, dto.email)
    if await _pendente_do_email(db, dto.email) is not None:
        raise AppError(
            codigo="SOLICITACAO_JA_PENDENTE",
            mensagem="Ja existe um pedido de acesso esperando aprovacao para este email.",
            status_code=409,
        )
    solicitacao = SolicitacaoAcesso(
        nome=dto.nome,
        email=dto.email,
        senha_hash=hash_senha(dto.senha),
        status=SolicitacaoStatus.PENDENTE,
    )
    db.add(solicitacao)
    await db.flush()
    return solicitacao


async def listar_solicitacoes(db: AsyncSession) -> list[SolicitacaoAcesso]:
    resultado = await db.scalars(
        select(SolicitacaoAcesso)
        .where(SolicitacaoAcesso.status == SolicitacaoStatus.PENDENTE)
        .order_by(SolicitacaoAcesso.criado_em)
    )
    return list(resultado.all())


async def _obter_pendente(db: AsyncSession, solicitacao_id: UUID) -> SolicitacaoAcesso:
    solicitacao = await db.get(SolicitacaoAcesso, solicitacao_id)
    if solicitacao is None:
        raise AppError(
            codigo="SOLICITACAO_NAO_ENCONTRADA",
            mensagem="Pedido de acesso nao encontrado.",
            status_code=404,
        )
    if solicitacao.status != SolicitacaoStatus.PENDENTE:
        raise AppError(
            codigo="SOLICITACAO_JA_DECIDIDA",
            mensagem="Este pedido de acesso ja foi aprovado ou recusado.",
            status_code=422,
        )
    return solicitacao


async def _decidir(
    db: AsyncSession,
    solicitacao: SolicitacaoAcesso,
    status: SolicitacaoStatus,
    *,
    usuario_id: UUID,
    acao: str,
    papel: Papel | None = None,
) -> None:
    solicitacao.status = status
    solicitacao.decidido_por_id = usuario_id
    solicitacao.decidido_em = datetime.now(UTC)
    await db.flush()
    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="solicitacao_acesso",
        entidade_id=solicitacao.id,
        acao=acao,
        antes={"status": SolicitacaoStatus.PENDENTE.value},
        depois={
            "status": status.value,
            "nome": solicitacao.nome,
            "email": solicitacao.email,
            **({"papel": papel.value} if papel else {}),
        },
    )


async def aprovar_solicitacao(
    db: AsyncSession,
    solicitacao_id: UUID,
    *,
    usuario_id: UUID,
    papel: Papel = Papel.ARBITRO,
) -> Usuario:
    solicitacao = await _obter_pendente(db, solicitacao_id)
    await _recusar_se_email_tem_conta(db, solicitacao.email)
    usuario = Usuario(
        nome=solicitacao.nome,
        email=solicitacao.email,
        senha_hash=solicitacao.senha_hash,
        papel=papel,
        ativo=True,
    )
    db.add(usuario)
    await db.flush()
    solicitacao.usuario_criado_id = usuario.id
    await _decidir(
        db,
        solicitacao,
        SolicitacaoStatus.APROVADA,
        usuario_id=usuario_id,
        acao="APROVAR_ACESSO",
        papel=papel,
    )
    return usuario


async def recusar_solicitacao(
    db: AsyncSession, solicitacao_id: UUID, *, usuario_id: UUID
) -> SolicitacaoAcesso:
    solicitacao = await _obter_pendente(db, solicitacao_id)
    await _decidir(
        db, solicitacao, SolicitacaoStatus.RECUSADA, usuario_id=usuario_id, acao="RECUSAR_ACESSO"
    )
    return solicitacao


async def tem_solicitacao_pendente(db: AsyncSession, email: str, senha: str) -> bool:
    """Pro login explicar "seu pedido ainda nao foi aprovado" em vez de
    "senha invalida". So responde sim com a senha certa do pedido."""
    solicitacao = await _pendente_do_email(db, email)
    return solicitacao is not None and verificar_senha(senha, solicitacao.senha_hash)
