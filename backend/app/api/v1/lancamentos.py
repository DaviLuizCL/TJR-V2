from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.lancamento import (
    LancamentoAuditoriaOut,
    LancamentoCorrigir,
    LancamentoCreate,
    LancamentoOut,
)
from app.services import lancamento as lancamento_service

router = APIRouter()

_PAPEIS_LANCAMENTO = (Papel.ARBITRO, Papel.COORDENADOR)
_PAPEIS_LEITURA = (Papel.ARBITRO, Papel.COORDENADOR, Papel.SECRETARIA)


@router.post("/lancamentos", response_model=LancamentoOut, status_code=201)
async def criar_lancamento(
    dto: LancamentoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LANCAMENTO)),
) -> LancamentoOut:
    lancamento = await lancamento_service.criar_lancamento(db, dto, arbitro_id=usuario.id)
    completo = await lancamento_service.obter_lancamento_completo(db, lancamento.id)
    return LancamentoOut.model_validate(completo)


@router.get("/lancamentos", response_model=Pagina[LancamentoOut])
async def listar_lancamentos(
    rodada_id: UUID | None = None,
    equipe_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[LancamentoOut]:
    itens, total = await lancamento_service.listar_lancamentos(
        db, rodada_id=rodada_id, equipe_id=equipe_id, page=page, size=size
    )
    completos = [await lancamento_service.obter_lancamento_completo(db, item.id) for item in itens]
    return Pagina(
        itens=[LancamentoOut.model_validate(item) for item in completos],
        total=total,
        page=page,
        size=size,
    )


@router.get("/lancamentos/auditoria", response_model=Pagina[LancamentoAuditoriaOut])
async def listar_auditoria(
    evento_id: UUID | None = None,
    modalidade_id: UUID | None = None,
    rodada_id: UUID | None = None,
    equipe_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[LancamentoAuditoriaOut]:
    itens, total = await lancamento_service.listar_lancamentos_auditoria(
        db,
        evento_id=evento_id,
        modalidade_id=modalidade_id,
        rodada_id=rodada_id,
        equipe_id=equipe_id,
        page=page,
        size=size,
    )
    return Pagina(itens=itens, total=total, page=page, size=size)


@router.get("/lancamentos/{lancamento_id}", response_model=LancamentoOut)
async def obter_lancamento(
    lancamento_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> LancamentoOut:
    lancamento = await lancamento_service.obter_lancamento_completo(db, lancamento_id)
    return LancamentoOut.model_validate(lancamento)


@router.post("/lancamentos/{lancamento_id}/confirmar", response_model=LancamentoOut)
async def confirmar_lancamento(
    lancamento_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LANCAMENTO)),
) -> LancamentoOut:
    await lancamento_service.confirmar_lancamento(db, lancamento_id, usuario_id=usuario.id)
    completo = await lancamento_service.obter_lancamento_completo(db, lancamento_id)
    return LancamentoOut.model_validate(completo)


@router.post("/lancamentos/{lancamento_id}/corrigir", response_model=LancamentoOut)
async def corrigir_lancamento(
    lancamento_id: UUID,
    dto: LancamentoCorrigir,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> LancamentoOut:
    await lancamento_service.corrigir_lancamento(db, lancamento_id, dto, usuario_id=usuario.id)
    completo = await lancamento_service.obter_lancamento_completo(db, lancamento_id)
    return LancamentoOut.model_validate(completo)
