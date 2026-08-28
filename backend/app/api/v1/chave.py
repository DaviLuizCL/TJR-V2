from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.chave import ChaveCreate, ChaveEquipeCreate, ChaveOut, ClassificacaoChaveItem
from app.services import chave as chave_service
from app.services import consolidacao as consolidacao_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/modalidades/{modalidade_id}/chaves", response_model=ChaveOut, status_code=201)
async def criar_chave(
    modalidade_id: UUID,
    dto: ChaveCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> ChaveOut:
    chave = await chave_service.criar_chave(db, dto, usuario_id=usuario.id)
    return ChaveOut(
        id=chave.id,
        modalidade_id=chave.modalidade_id,
        nivel=chave.nivel,
        nome=chave.nome,
        equipe_ids=[],
    )


@router.get("/modalidades/{modalidade_id}/chaves", response_model=list[ChaveOut])
async def listar_chaves(
    modalidade_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> list[ChaveOut]:
    itens = await chave_service.listar_chaves(db, modalidade_id)
    return [
        ChaveOut(
            id=chave.id,
            modalidade_id=chave.modalidade_id,
            nivel=chave.nivel,
            nome=chave.nome,
            equipe_ids=equipe_ids,
        )
        for chave, equipe_ids in itens
    ]


@router.post("/chaves/{chave_id}/equipes", status_code=201)
async def adicionar_equipe(
    chave_id: UUID,
    dto: ChaveEquipeCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await chave_service.adicionar_equipe(db, chave_id, dto.equipe_id, usuario_id=usuario.id)
    return Response(status_code=201)


@router.delete("/chaves/{chave_id}/equipes/{equipe_id}", status_code=204)
async def remover_equipe(
    chave_id: UUID,
    equipe_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await chave_service.remover_equipe(db, chave_id, equipe_id, usuario_id=usuario.id)
    return Response(status_code=204)


@router.get("/chaves/{chave_id}/classificacao", response_model=list[ClassificacaoChaveItem])
async def obter_classificacao_chave(
    chave_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> list[ClassificacaoChaveItem]:
    resultado = await consolidacao_service.calcular_classificacao_chave(db, chave_id)
    return [
        ClassificacaoChaveItem(
            equipe_id=item["equipe_id"],
            nota_final=float(item["nota_final"]),
            vitorias=item["vitorias"],
            empates=item["empates"],
            derrotas=item["derrotas"],
            posicao=item["posicao"],
        )
        for item in resultado
    ]
