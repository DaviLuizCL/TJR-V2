from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.common import Pagina
from app.schemas.inscricao import DefinirOrdemIn, InscricaoCreate, InscricaoOut, SortearOrdemIn
from app.services import inscricao as inscricao_service
from app.services import ordem_apresentacao as ordem_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/inscricoes", response_model=InscricaoOut, status_code=201)
async def criar_inscricao(
    dto: InscricaoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> InscricaoOut:
    inscricao = await inscricao_service.criar_inscricao(db, dto, usuario_id=usuario.id)
    return InscricaoOut.model_validate(inscricao)


@router.get("/inscricoes", response_model=Pagina[InscricaoOut])
async def listar_inscricoes(
    modalidade_id: UUID | None = None,
    equipe_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[InscricaoOut]:
    itens, total = await inscricao_service.listar_inscricoes(
        db, modalidade_id=modalidade_id, equipe_id=equipe_id, page=page, size=size
    )
    return Pagina(
        itens=[InscricaoOut.model_validate(item) for item in itens],
        total=total,
        page=page,
        size=size,
    )


@router.delete("/inscricoes/{inscricao_id}", status_code=204)
async def deletar_inscricao(
    inscricao_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await inscricao_service.deletar_inscricao(db, inscricao_id, usuario_id=usuario.id)
    return Response(status_code=204)


@router.post("/modalidades/{modalidade_id}/ordem-apresentacao/sortear", status_code=204)
async def sortear_ordem_apresentacao(
    modalidade_id: UUID,
    dto: SortearOrdemIn,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await ordem_service.sortear_ordem(db, modalidade_id, nivel=dto.nivel, usuario_id=usuario.id)
    return Response(status_code=204)


@router.put("/modalidades/{modalidade_id}/ordem-apresentacao", status_code=204)
async def definir_ordem_apresentacao(
    modalidade_id: UUID,
    dto: DefinirOrdemIn,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    await ordem_service.definir_ordem(
        db, modalidade_id, nivel=dto.nivel, equipe_ids=dto.equipe_ids, usuario_id=usuario.id
    )
    return Response(status_code=204)


@router.get(
    "/modalidades/{modalidade_id}/sequencia-competicao.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def baixar_sequencia_competicao_pdf(
    modalidade_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Response:
    pdf = await ordem_service.gerar_sequencia_pdf(db, modalidade_id)
    nome = f"sequencia-competicao-{modalidade_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
