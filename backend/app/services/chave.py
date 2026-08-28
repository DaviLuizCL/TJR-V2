from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.chave import Chave, ChaveEquipe
from app.models.inscricao import Inscricao
from app.models.modalidade import TipoDisputa
from app.models.partida import Partida
from app.schemas.chave import ChaveCreate
from app.services.audit import registrar_audit_log
from app.services.equipe import obter_equipe
from app.services.modalidade import obter_modalidade


async def criar_chave(db: AsyncSession, dto: ChaveCreate, *, usuario_id: UUID) -> Chave:
    modalidade = await obter_modalidade(db, dto.modalidade_id)
    if modalidade.tipo_disputa != TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="MODALIDADE_NAO_E_CONFRONTO",
            mensagem="Chave so pode ser criada para modalidade de confronto.",
            status_code=422,
        )
    if dto.nivel not in modalidade.niveis_aplicaveis:
        raise AppError(
            codigo="NIVEL_FORA_DOS_APLICAVEIS",
            mensagem="Nivel informado nao esta entre os niveis aplicaveis da modalidade.",
            status_code=422,
        )

    chave = Chave(modalidade_id=modalidade.id, nivel=dto.nivel, nome=dto.nome)
    db.add(chave)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="chave",
        entidade_id=chave.id,
        acao="CRIAR",
        antes=None,
        depois={"modalidade_id": str(modalidade.id), "nivel": chave.nivel, "nome": chave.nome},
    )
    return chave


async def obter_chave(db: AsyncSession, chave_id: UUID) -> Chave:
    chave = await db.get(Chave, chave_id)
    if chave is None:
        raise AppError(
            codigo="CHAVE_NAO_ENCONTRADA", mensagem="Chave nao encontrada.", status_code=404
        )
    return chave


async def adicionar_equipe(
    db: AsyncSession, chave_id: UUID, equipe_id: UUID, *, usuario_id: UUID
) -> ChaveEquipe:
    chave = await obter_chave(db, chave_id)
    equipe = await obter_equipe(db, equipe_id)

    if equipe.nivel != chave.nivel:
        raise AppError(
            codigo="NIVEIS_INCOMPATIVEIS",
            mensagem="A equipe precisa ser do mesmo nivel da chave.",
            status_code=422,
        )

    inscrita = await db.scalar(
        select(Inscricao).where(
            Inscricao.equipe_id == equipe.id, Inscricao.modalidade_id == chave.modalidade_id
        )
    )
    if inscrita is None:
        raise AppError(
            codigo="EQUIPE_NAO_INSCRITA",
            mensagem=f"A equipe '{equipe.nome}' nao esta inscrita nesta modalidade.",
            status_code=422,
        )

    ja_tem_chave = await db.scalar(
        select(ChaveEquipe.id)
        .join(Chave, ChaveEquipe.chave_id == Chave.id)
        .where(Chave.modalidade_id == chave.modalidade_id, ChaveEquipe.equipe_id == equipe.id)
        .limit(1)
    )
    if ja_tem_chave is not None:
        raise AppError(
            codigo="EQUIPE_JA_TEM_CHAVE",
            mensagem="Esta equipe ja esta em outra chave desta modalidade.",
            status_code=409,
        )

    vinculo = ChaveEquipe(chave_id=chave.id, equipe_id=equipe.id)
    db.add(vinculo)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="chave_equipe",
        entidade_id=vinculo.id,
        acao="ADICIONAR_EQUIPE",
        antes=None,
        depois={"chave_id": str(chave.id), "equipe_id": str(equipe.id)},
    )
    return vinculo


async def _chave_tem_partida(db: AsyncSession, chave_id: UUID) -> bool:
    return (
        await db.scalar(select(Partida.id).where(Partida.chave_id == chave_id).limit(1))
    ) is not None


async def remover_equipe(
    db: AsyncSession, chave_id: UUID, equipe_id: UUID, *, usuario_id: UUID
) -> None:
    chave = await obter_chave(db, chave_id)

    if await _chave_tem_partida(db, chave.id):
        raise AppError(
            codigo="CHAVE_JA_TEM_PARTIDA",
            mensagem="Esta chave ja tem partida gerada; use o reset de chaveamento pra corrigir.",
            status_code=409,
        )

    vinculo = await db.scalar(
        select(ChaveEquipe).where(
            ChaveEquipe.chave_id == chave.id, ChaveEquipe.equipe_id == equipe_id
        )
    )
    if vinculo is None:
        return

    await db.delete(vinculo)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="chave_equipe",
        entidade_id=vinculo.id,
        acao="REMOVER_EQUIPE",
        antes={"chave_id": str(chave.id), "equipe_id": str(equipe_id)},
        depois=None,
    )


async def listar_chaves(db: AsyncSession, modalidade_id: UUID) -> list[tuple[Chave, list[UUID]]]:
    chaves = list(
        (await db.execute(select(Chave).where(Chave.modalidade_id == modalidade_id)))
        .scalars()
        .all()
    )
    resultado: list[tuple[Chave, list[UUID]]] = []
    for chave in chaves:
        equipe_ids = list(
            (
                await db.execute(
                    select(ChaveEquipe.equipe_id).where(ChaveEquipe.chave_id == chave.id)
                )
            )
            .scalars()
            .all()
        )
        resultado.append((chave, equipe_ids))
    return resultado
