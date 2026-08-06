from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo, ModificadorTipo
from app.schemas.criterio import CriterioCreate, CriterioUpdate
from app.services.audit import registrar_audit_log
from app.services.ficha import clonar_ficha_se_publicada, obter_ficha
from app.services.grupo import obter_grupo


def _validar_campos(
    *,
    categoria: CategoriaCriterio,
    tipo: CriterioTipo,
    pontos: float | None,
    valores_permitidos: list | None,
    modificador_tipo: ModificadorTipo | None,
    modificador_valor: float | None,
) -> None:
    if tipo in (CriterioTipo.CONTADOR, CriterioTipo.BOOLEANO):
        if pontos is None:
            raise AppError(
                codigo="CRITERIO_PONTOS_OBRIGATORIO",
                mensagem="pontos e obrigatorio para este tipo de criterio.",
                status_code=422,
            )

    if tipo == CriterioTipo.ESCALA:
        if not valores_permitidos:
            raise AppError(
                codigo="CRITERIO_VALORES_PERMITIDOS_OBRIGATORIO",
                mensagem="valores_permitidos e obrigatorio para criterio ESCALA.",
                status_code=422,
            )
        if list(valores_permitidos) != sorted(valores_permitidos) or len(
            set(valores_permitidos)
        ) != len(valores_permitidos):
            raise AppError(
                codigo="CRITERIO_VALORES_PERMITIDOS_INVALIDO",
                mensagem="valores_permitidos deve estar ordenado e sem repeticao.",
                status_code=422,
            )

    if tipo == CriterioTipo.MODIFICADOR:
        if modificador_tipo is None:
            raise AppError(
                codigo="CRITERIO_MODIFICADOR_TIPO_OBRIGATORIO",
                mensagem="modificador_tipo e obrigatorio para criterio MODIFICADOR.",
                status_code=422,
            )
        if modificador_tipo == ModificadorTipo.ZERA_TOTAL:
            if categoria != CategoriaCriterio.PENALIDADE:
                raise AppError(
                    codigo="CRITERIO_ZERA_TOTAL_APENAS_PENALIDADE",
                    mensagem="ZERA_TOTAL so e valido quando a categoria e PENALIDADE.",
                    status_code=422,
                )
        if modificador_tipo == ModificadorTipo.PERCENTUAL:
            if modificador_valor is None or not (0 <= modificador_valor <= 100):
                raise AppError(
                    codigo="CRITERIO_MODIFICADOR_VALOR_INVALIDO",
                    mensagem="modificador_valor deve estar entre 0 e 100 para PERCENTUAL.",
                    status_code=422,
                )


def _serializar(criterio: Criterio) -> dict:
    return {
        "grupo_id": str(criterio.grupo_id),
        "nome": criterio.nome,
        "categoria": criterio.categoria.value,
        "tipo": criterio.tipo.value,
        "pontos": str(criterio.pontos) if criterio.pontos is not None else None,
        "valores_permitidos": criterio.valores_permitidos,
        "max_ocorrencias": criterio.max_ocorrencias,
        "modificador_tipo": criterio.modificador_tipo.value if criterio.modificador_tipo else None,
        "modificador_valor": (
            str(criterio.modificador_valor) if criterio.modificador_valor is not None else None
        ),
        "ordem": criterio.ordem,
        "ativo": criterio.ativo,
    }


async def obter_criterio(db: AsyncSession, criterio_id: UUID) -> Criterio:
    criterio = await db.get(Criterio, criterio_id)
    if criterio is None:
        raise AppError(
            codigo="CRITERIO_NAO_ENCONTRADO", mensagem="Criterio nao encontrado.", status_code=404
        )
    return criterio


async def criar_criterio(
    db: AsyncSession, grupo_id: UUID, dto: CriterioCreate, *, usuario_id: UUID
) -> Criterio:
    grupo = await obter_grupo(db, grupo_id)
    ficha = await obter_ficha(db, grupo.ficha_id)
    ficha_alvo, mapa_grupos, _ = await clonar_ficha_se_publicada(db, ficha, usuario_id=usuario_id)

    if ficha_alvo.id != ficha.id:
        grupo = await obter_grupo(db, mapa_grupos[grupo.id])

    _validar_campos(
        categoria=dto.categoria,
        tipo=dto.tipo,
        pontos=dto.pontos,
        valores_permitidos=dto.valores_permitidos,
        modificador_tipo=dto.modificador_tipo,
        modificador_valor=dto.modificador_valor,
    )

    criterio = Criterio(
        grupo_id=grupo.id,
        nome=dto.nome,
        descricao=dto.descricao,
        categoria=dto.categoria,
        tipo=dto.tipo,
        pontos=dto.pontos,
        valores_permitidos=dto.valores_permitidos,
        max_ocorrencias=dto.max_ocorrencias,
        modificador_tipo=dto.modificador_tipo,
        modificador_valor=dto.modificador_valor,
        ordem=dto.ordem,
        ativo=dto.ativo,
    )
    db.add(criterio)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="criterio",
        entidade_id=criterio.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(criterio),
    )
    return criterio


async def atualizar_criterio(
    db: AsyncSession, criterio_id: UUID, dto: CriterioUpdate, *, usuario_id: UUID
) -> Criterio:
    criterio = await obter_criterio(db, criterio_id)
    grupo = await obter_grupo(db, criterio.grupo_id)
    ficha = await obter_ficha(db, grupo.ficha_id)
    ficha_alvo, _, mapa_criterios = await clonar_ficha_se_publicada(
        db, ficha, usuario_id=usuario_id
    )

    if ficha_alvo.id != ficha.id:
        criterio = await obter_criterio(db, mapa_criterios[criterio.id])

    antes = _serializar(criterio)
    dados = dto.model_dump(exclude_unset=True)

    _validar_campos(
        categoria=dados.get("categoria", criterio.categoria),
        tipo=dados.get("tipo", criterio.tipo),
        pontos=dados.get("pontos", criterio.pontos),
        valores_permitidos=dados.get("valores_permitidos", criterio.valores_permitidos),
        modificador_tipo=dados.get("modificador_tipo", criterio.modificador_tipo),
        modificador_valor=dados.get("modificador_valor", criterio.modificador_valor),
    )

    for campo, valor in dados.items():
        setattr(criterio, campo, valor)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="criterio",
        entidade_id=criterio.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(criterio),
    )
    return criterio


async def deletar_criterio(db: AsyncSession, criterio_id: UUID, *, usuario_id: UUID) -> None:
    criterio = await obter_criterio(db, criterio_id)
    grupo = await obter_grupo(db, criterio.grupo_id)
    ficha = await obter_ficha(db, grupo.ficha_id)
    ficha_alvo, _, mapa_criterios = await clonar_ficha_se_publicada(
        db, ficha, usuario_id=usuario_id
    )

    if ficha_alvo.id != ficha.id:
        criterio = await obter_criterio(db, mapa_criterios[criterio.id])

    antes = _serializar(criterio)
    await db.delete(criterio)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="criterio",
        entidade_id=criterio.id,
        acao="DELETAR",
        antes=antes,
        depois=None,
    )
