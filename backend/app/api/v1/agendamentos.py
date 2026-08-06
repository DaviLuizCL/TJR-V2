from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import exigir_papel
from app.db.session import get_db
from app.models.usuario import Papel, Usuario
from app.schemas.agendamento import AgendamentoOut, GerarAgendamentosRequest
from app.schemas.common import Pagina
from app.services import agendamento as agendamento_service

router = APIRouter()

_PAPEIS_LEITURA = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.post("/agendamentos/gerar", response_model=list[AgendamentoOut])
async def gerar_agendamentos(
    dto: GerarAgendamentosRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(Papel.COORDENADOR)),
) -> list[AgendamentoOut]:
    agendamentos = await agendamento_service.gerar_agendamentos(
        db,
        dto.modalidade_id,
        dto.rodada_ids,
        dto.horario_inicio,
        regenerar=dto.regenerar,
        usuario_id=usuario.id,
    )
    return [AgendamentoOut.model_validate(a) for a in agendamentos]


@router.get("/agendamentos", response_model=Pagina[AgendamentoOut])
async def listar_agendamentos(
    modalidade_id: UUID | None = None,
    rodada_id: UUID | None = None,
    arena_id: UUID | None = None,
    equipe_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_papel(*_PAPEIS_LEITURA)),
) -> Pagina[AgendamentoOut]:
    itens, total = await agendamento_service.listar_agendamentos(
        db,
        modalidade_id=modalidade_id,
        rodada_id=rodada_id,
        arena_id=arena_id,
        equipe_id=equipe_id,
        page=page,
        size=size,
    )
    return Pagina(
        itens=[AgendamentoOut.model_validate(item) for item in itens],
        total=total,
        page=page,
        size=size,
    )
