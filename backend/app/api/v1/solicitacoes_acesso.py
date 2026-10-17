from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel, obter_papel_atual
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.solicitacao_acesso import (
    AprovarSolicitacaoIn,
    SolicitacaoAcessoCreate,
    SolicitacaoAcessoOut,
)
from app.schemas.usuario import UsuarioOut
from app.services import solicitacao_acesso as solicitacao_service

router = APIRouter()


@router.post("/solicitacoes-acesso", response_model=SolicitacaoAcessoOut, status_code=201)
async def solicitar_acesso(
    dados: SolicitacaoAcessoCreate,
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> SolicitacaoAcessoOut:
    # Aberto pra PUBLICO (sem login): o pedido sozinho nao da acesso a nada.
    solicitacao = await solicitacao_service.solicitar_acesso(db, dados)
    return SolicitacaoAcessoOut.model_validate(solicitacao)


@router.get("/solicitacoes-acesso", response_model=list[SolicitacaoAcessoOut])
async def listar_solicitacoes(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> list[SolicitacaoAcessoOut]:
    solicitacoes = await solicitacao_service.listar_solicitacoes(db)
    return [SolicitacaoAcessoOut.model_validate(s) for s in solicitacoes]


@router.post("/solicitacoes-acesso/{solicitacao_id}/aprovar", response_model=UsuarioOut)
async def aprovar_solicitacao(
    solicitacao_id: UUID,
    dados: AprovarSolicitacaoIn | None = None,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> UsuarioOut:
    papel = Papel(dados.papel) if dados else Papel.ARBITRO
    criado = await solicitacao_service.aprovar_solicitacao(
        db, solicitacao_id, usuario_id=usuario.id, papel=papel
    )
    return UsuarioOut.model_validate(criado)


@router.post("/solicitacoes-acesso/{solicitacao_id}/recusar", status_code=204)
async def recusar_solicitacao(
    solicitacao_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await solicitacao_service.recusar_solicitacao(db, solicitacao_id, usuario_id=usuario.id)
    return Response(status_code=204)
