from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import obter_papel_atual
from app.core.errors import AppError
from app.db.session import get_db
from app.models.equipe import Equipe
from app.models.usuario import Papel
from app.schemas.ranking import ClassificacaoItemOut, RankingModalidadeResumoOut, RankingOut
from app.services import consolidacao as consolidacao_service
from app.services import modalidade as modalidade_service

router = APIRouter()

_PAPEIS_STAFF = (Papel.COORDENADOR, Papel.ARBITRO, Papel.SECRETARIA)


@router.get("/ranking/modalidades", response_model=list[RankingModalidadeResumoOut])
async def listar_modalidades_com_ranking_liberado(
    evento_id: UUID,
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> list[RankingModalidadeResumoOut]:
    itens, _total = await modalidade_service.listar_modalidades(
        db, evento_id=evento_id, page=1, size=200
    )
    liberadas = [modalidade for modalidade in itens if modalidade.ranking_liberado]
    return [RankingModalidadeResumoOut.model_validate(m) for m in liberadas]


@router.get("/ranking/modalidades/{modalidade_id}", response_model=RankingOut)
async def obter_ranking(
    modalidade_id: UUID,
    db: AsyncSession = Depends(get_db),
    papel: Papel = Depends(obter_papel_atual),
) -> RankingOut:
    modalidade = await modalidade_service.obter_modalidade(db, modalidade_id)

    if not modalidade.ranking_liberado and papel not in _PAPEIS_STAFF:
        raise AppError(
            codigo="RANKING_NAO_LIBERADO",
            mensagem="O ranking desta modalidade ainda nao foi liberado pela coordenacao.",
            status_code=403,
        )

    classificacao = await consolidacao_service.calcular_classificacao(db, modalidade_id)

    equipe_ids = [item["equipe_id"] for item in classificacao]
    equipes_por_id: dict[UUID, Equipe] = {}
    if equipe_ids:
        resultado = await db.execute(select(Equipe).where(Equipe.id.in_(equipe_ids)))
        equipes_por_id = {equipe.id: equipe for equipe in resultado.scalars().all()}

    itens = [
        ClassificacaoItemOut(
            equipe_id=item["equipe_id"],
            equipe_nome=equipes_por_id[item["equipe_id"]].nome
            if item["equipe_id"] in equipes_por_id
            else "",
            equipe_nivel=equipes_por_id[item["equipe_id"]].nivel
            if item["equipe_id"] in equipes_por_id
            else None,
            nota_final=float(item["nota_final"]),
            vitorias=item["vitorias"],
            empates=item["empates"],
            derrotas=item["derrotas"],
            eliminado_por_nome=(
                equipes_por_id[item["eliminado_por_equipe_id"]].nome
                if item["eliminado_por_equipe_id"] in equipes_por_id
                else None
            ),
            posicao=item["posicao"],
        )
        for item in classificacao
    ]

    return RankingOut(
        modalidade_id=modalidade.id,
        modalidade_nome=modalidade.nome,
        tipo_disputa=modalidade.tipo_disputa.value,
        formato_chaveamento=(
            modalidade.formato_chaveamento.value if modalidade.formato_chaveamento else None
        ),
        ranking_liberado=modalidade.ranking_liberado,
        itens=itens,
    )
