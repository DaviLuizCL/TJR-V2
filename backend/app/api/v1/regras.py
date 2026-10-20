from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel, obter_papel_atual
from app.db.session import get_db
from app.models.regra_modalidade import TipoRegra
from app.models.usuario import Papel, Usuario
from app.schemas.regra_modalidade import ModalidadeComRegrasOut, RegraResumoOut
from app.services import regra_modalidade as regra_service
from app.services.publico import _evento_unico_id

router = APIRouter()


@router.put("/modalidades/{modalidade_id}/regras/{tipo}", response_model=RegraResumoOut)
async def enviar_regra(
    modalidade_id: UUID,
    tipo: TipoRegra,
    arquivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> RegraResumoOut:
    regra = await regra_service.enviar_regra(
        db,
        modalidade_id,
        tipo,
        nome_arquivo=arquivo.filename or "regra.pdf",
        conteudo=await arquivo.read(),
        usuario_id=usuario.id,
    )
    return RegraResumoOut.model_validate(regra)


@router.delete("/modalidades/{modalidade_id}/regras/{tipo}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_regra(
    modalidade_id: UUID,
    tipo: TipoRegra,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> None:
    await regra_service.remover_regra(db, modalidade_id, tipo)


@router.get("/publico/regras", response_model=list[ModalidadeComRegrasOut])
async def listar_regras_publicas(
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> list[ModalidadeComRegrasOut]:
    # Aberto pra qualquer papel, inclusive PUBLICO: regra e pra todo mundo ler.
    modalidades = await regra_service.listar_regras_do_evento(db, await _evento_unico_id(db))
    return [ModalidadeComRegrasOut.model_validate(m) for m in modalidades]


@router.get(
    "/publico/modalidades/{modalidade_id}/regras/{tipo}",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def baixar_regra(
    modalidade_id: UUID,
    tipo: TipoRegra,
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> Response:
    regra = await regra_service.obter_regra(db, modalidade_id, tipo)
    # inline: o celular abre o PDF direto no navegador em vez de so baixar.
    return Response(
        content=regra.conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(regra.nome_arquivo)}"},
    )
