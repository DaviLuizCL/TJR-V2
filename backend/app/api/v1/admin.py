from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.checklist import ChecklistOut
from app.services import backup as backup_service
from app.services import checklist as checklist_service
from app.services import importacao as importacao_service
from app.services.importacao import RelatorioImportacao

router = APIRouter()


@router.get("/admin/checklist", response_model=ChecklistOut)
async def obter_checklist(
    evento_id: UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR, Papel.SECRETARIA)),
) -> ChecklistOut:
    return await checklist_service.gerar_checklist(db, evento_id)


@router.post("/admin/importar-equipes", response_model=RelatorioImportacao)
async def importar_equipes(
    evento_id: UUID,
    simular: bool = True,
    arquivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> RelatorioImportacao:
    conteudo = await arquivo.read()
    return await importacao_service.importar_planilha(
        db, conteudo, evento_id=evento_id, usuario_id=usuario.id, simular=simular
    )


@router.get(
    "/admin/backup",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def baixar_backup(
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> Response:
    conteudo = await backup_service.gerar_backup(settings.database_url)
    agora = datetime.now(UTC).astimezone(ZoneInfo("America/Fortaleza"))
    nome = f"tjr-backup-{agora:%Y-%m-%d-%H%M}.dump"
    return Response(
        content=conteudo,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
