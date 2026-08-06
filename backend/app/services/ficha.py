from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.criterio import Criterio
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.lancamento import Lancamento
from app.schemas.ficha import FichaCreate
from app.services.audit import registrar_audit_log
from app.services.modalidade import obter_modalidade


def _serializar(ficha: Ficha) -> dict:
    return {
        "modalidade_id": str(ficha.modalidade_id),
        "nivel": ficha.nivel,
        "versao": ficha.versao,
        "status": ficha.status.value,
        "publicada_em": ficha.publicada_em.isoformat() if ficha.publicada_em else None,
    }


async def criar_ficha(db: AsyncSession, dto: FichaCreate, *, usuario_id: UUID) -> Ficha:
    modalidade = await obter_modalidade(db, dto.modalidade_id)

    if modalidade.ficha_unica_entre_niveis:
        if dto.nivel is not None:
            raise AppError(
                codigo="FICHA_NIVEL_NAO_PERMITIDO",
                mensagem="Esta modalidade usa ficha unica entre niveis; nao informe nivel.",
                status_code=422,
            )
    else:
        if dto.nivel is None:
            raise AppError(
                codigo="FICHA_NIVEL_OBRIGATORIO",
                mensagem="Esta modalidade exige ficha por nivel; informe o nivel.",
                status_code=422,
            )
        if dto.nivel not in modalidade.niveis_aplicaveis:
            raise AppError(
                codigo="FICHA_NIVEL_FORA_DOS_APLICAVEIS",
                mensagem="Nivel informado nao esta entre os niveis aplicaveis da modalidade.",
                status_code=422,
            )

    resultado = await db.execute(
        select(Ficha).where(
            Ficha.modalidade_id == dto.modalidade_id,
            Ficha.nivel == dto.nivel,
            Ficha.status != FichaStatus.SUBSTITUIDA,
        )
    )
    if resultado.scalar_one_or_none() is not None:
        raise AppError(
            codigo="FICHA_JA_EXISTE_PARA_NIVEL",
            mensagem="Ja existe uma ficha ativa para este nivel nesta modalidade.",
            status_code=409,
        )

    ficha = Ficha(
        modalidade_id=dto.modalidade_id, nivel=dto.nivel, versao=1, status=FichaStatus.RASCUNHO
    )
    db.add(ficha)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="ficha",
        entidade_id=ficha.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(ficha),
    )
    return ficha


async def obter_ficha(db: AsyncSession, ficha_id: UUID) -> Ficha:
    ficha = await db.get(Ficha, ficha_id)
    if ficha is None:
        raise AppError(
            codigo="FICHA_NAO_ENCONTRADA", mensagem="Ficha nao encontrada.", status_code=404
        )
    return ficha


async def obter_ficha_completa(db: AsyncSession, ficha_id: UUID) -> Ficha:
    ficha = await obter_ficha(db, ficha_id)

    resultado = await db.execute(
        select(Grupo).where(Grupo.ficha_id == ficha.id).order_by(Grupo.ordem)
    )
    grupos = list(resultado.scalars().all())

    for grupo in grupos:
        resultado_c = await db.execute(
            select(Criterio).where(Criterio.grupo_id == grupo.id).order_by(Criterio.ordem)
        )
        grupo.criterios = list(resultado_c.scalars().all())

    ficha.grupos = grupos
    return ficha


async def listar_fichas(
    db: AsyncSession, *, modalidade_id: UUID | None, nivel: int | None, page: int, size: int
) -> tuple[list[Ficha], int]:
    stmt = select(Ficha)
    count_stmt = select(func.count()).select_from(Ficha)

    if modalidade_id is not None:
        stmt = stmt.where(Ficha.modalidade_id == modalidade_id)
        count_stmt = count_stmt.where(Ficha.modalidade_id == modalidade_id)
    if nivel is not None:
        stmt = stmt.where(Ficha.nivel == nivel)
        count_stmt = count_stmt.where(Ficha.nivel == nivel)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(
        stmt.order_by(Ficha.criado_em.desc()).offset((page - 1) * size).limit(size)
    )
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def clonar_ficha_se_publicada(
    db: AsyncSession, ficha: Ficha, *, usuario_id: UUID
) -> tuple[Ficha, dict[UUID, UUID], dict[UUID, UUID]]:
    """Se `ficha` estiver PUBLICADA, clona ficha+grupos+criterios como nova versao
    (PUBLICADA) e marca a original como SUBSTITUIDA. Devolve a ficha em que a
    proxima edicao deve ocorrer, junto dos mapas old_id->new_id de grupos e
    criterios, para quem precisar redirecionar uma edicao pontual.

    Se `ficha` ja estiver RASCUNHO, devolve ela mesma e mapas vazios (edita no lugar).
    """
    if ficha.status != FichaStatus.PUBLICADA:
        return ficha, {}, {}

    nova_ficha = Ficha(
        modalidade_id=ficha.modalidade_id,
        nivel=ficha.nivel,
        versao=ficha.versao + 1,
        status=FichaStatus.PUBLICADA,
        publicada_em=datetime.now(UTC),
    )
    db.add(nova_ficha)
    await db.flush()

    resultado = await db.execute(
        select(Grupo).where(Grupo.ficha_id == ficha.id).order_by(Grupo.ordem)
    )
    grupos_antigos = resultado.scalars().all()

    mapa_grupos: dict[UUID, UUID] = {}
    mapa_criterios: dict[UUID, UUID] = {}

    for grupo_antigo in grupos_antigos:
        novo_grupo = Grupo(ficha_id=nova_ficha.id, nome=grupo_antigo.nome, ordem=grupo_antigo.ordem)
        db.add(novo_grupo)
        await db.flush()
        mapa_grupos[grupo_antigo.id] = novo_grupo.id

        resultado_c = await db.execute(
            select(Criterio).where(Criterio.grupo_id == grupo_antigo.id).order_by(Criterio.ordem)
        )
        for c in resultado_c.scalars().all():
            novo_criterio = Criterio(
                grupo_id=novo_grupo.id,
                nome=c.nome,
                descricao=c.descricao,
                categoria=c.categoria,
                tipo=c.tipo,
                pontos=c.pontos,
                valores_permitidos=c.valores_permitidos,
                max_ocorrencias=c.max_ocorrencias,
                modificador_tipo=c.modificador_tipo,
                modificador_valor=c.modificador_valor,
                ordem=c.ordem,
                ativo=c.ativo,
            )
            db.add(novo_criterio)
            await db.flush()
            mapa_criterios[c.id] = novo_criterio.id

    antes = _serializar(ficha)
    ficha.status = FichaStatus.SUBSTITUIDA
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="ficha",
        entidade_id=ficha.id,
        acao="SUBSTITUIR",
        antes=antes,
        depois=_serializar(nova_ficha),
    )

    return nova_ficha, mapa_grupos, mapa_criterios


async def excluir_ficha(db: AsyncSession, ficha_id: UUID, *, usuario_id: UUID) -> None:
    """Remove a ficha de verdade, mas so quando nenhum lancamento ja usou ela.

    Se ha lancamento apontando pra essa ficha, a pontuacao lancada precisa ficar
    guardada pra auditoria (regra invioravel 5) - nesse caso o caminho e
    `depreciar_ficha`, nao a exclusao.
    """
    ficha = await obter_ficha(db, ficha_id)

    tem_lancamento = await db.scalar(
        select(func.count()).select_from(Lancamento).where(Lancamento.ficha_id == ficha_id)
    )
    if tem_lancamento:
        raise AppError(
            codigo="FICHA_POSSUI_LANCAMENTOS",
            mensagem=(
                "Esta ficha ja tem lancamento registrado e nao pode ser excluida. "
                "Use depreciar para tira-la do calculo do ranking mantendo o historico."
            ),
            status_code=409,
        )

    antes = _serializar(ficha)

    resultado = await db.execute(select(Grupo.id).where(Grupo.ficha_id == ficha_id))
    grupo_ids = [row[0] for row in resultado.all()]
    if grupo_ids:
        await db.execute(delete(Criterio).where(Criterio.grupo_id.in_(grupo_ids)))
        await db.execute(delete(Grupo).where(Grupo.ficha_id == ficha_id))
    await db.delete(ficha)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="ficha",
        entidade_id=ficha_id,
        acao="EXCLUIR",
        antes=antes,
        depois=None,
    )


async def depreciar_ficha(db: AsyncSession, ficha_id: UUID, *, usuario_id: UUID) -> Ficha:
    """Marca a ficha como DEPRECADA: seus lancamentos ficam guardados (auditoria)
    mas saem do calculo de consolidacao/ranking.
    """
    ficha = await obter_ficha(db, ficha_id)

    if ficha.status == FichaStatus.RASCUNHO:
        raise AppError(
            codigo="FICHA_RASCUNHO_NAO_PODE_SER_DEPRECIADA",
            mensagem="Ficha em RASCUNHO nunca teve lancamento; exclua-a em vez de depreciar.",
            status_code=422,
        )
    if ficha.status == FichaStatus.DEPRECADA:
        raise AppError(
            codigo="FICHA_JA_DEPRECIADA",
            mensagem="Esta ficha ja esta depreciada.",
            status_code=422,
        )

    antes = _serializar(ficha)
    ficha.status = FichaStatus.DEPRECADA
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="ficha",
        entidade_id=ficha.id,
        acao="DEPRECIAR",
        antes=antes,
        depois=_serializar(ficha),
    )
    return ficha


async def publicar_ficha(db: AsyncSession, ficha_id: UUID, *, usuario_id: UUID) -> Ficha:
    ficha = await obter_ficha(db, ficha_id)
    if ficha.status != FichaStatus.RASCUNHO:
        raise AppError(
            codigo="FICHA_NAO_PODE_SER_PUBLICADA",
            mensagem="Somente uma ficha em RASCUNHO pode ser publicada.",
            status_code=422,
        )

    antes = _serializar(ficha)
    ficha.status = FichaStatus.PUBLICADA
    ficha.publicada_em = datetime.now(UTC)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="ficha",
        entidade_id=ficha.id,
        acao="PUBLICAR",
        antes=antes,
        depois=_serializar(ficha),
    )
    return ficha
