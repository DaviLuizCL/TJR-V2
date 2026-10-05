from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.modalidade import TipoDisputa
from app.models.rodada import ModoHorario, Rodada, RodadaStatus
from app.schemas.rodada import RodadaCreate, RodadaUpdate
from app.services.audit import registrar_audit_log
from app.services.modalidade import obter_modalidade


def _serializar(rodada: Rodada) -> dict:
    return {
        "modalidade_id": str(rodada.modalidade_id),
        "numero": rodada.numero,
        "modo_horario": rodada.modo_horario.value,
        "horario_inicio": rodada.horario_inicio.isoformat() if rodada.horario_inicio else None,
        "status": rodada.status.value,
    }


def _validar_horario(modo_horario: ModoHorario, horario_inicio) -> None:
    if modo_horario == ModoHorario.MANUAL and horario_inicio is None:
        raise AppError(
            codigo="HORARIO_INICIO_OBRIGATORIO",
            mensagem="horario_inicio e obrigatorio quando modo_horario e MANUAL.",
            status_code=422,
        )


async def criar_rodada(db: AsyncSession, dto: RodadaCreate, *, usuario_id: UUID) -> Rodada:
    modalidade = await obter_modalidade(db, dto.modalidade_id)

    if not (1 <= dto.numero <= modalidade.qtd_rodadas):
        raise AppError(
            codigo="NUMERO_RODADA_INVALIDO",
            mensagem=f"numero deve estar entre 1 e {modalidade.qtd_rodadas}.",
            status_code=422,
        )

    duplicada = await db.scalar(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id, Rodada.numero == dto.numero)
    )
    if duplicada is not None:
        raise AppError(
            codigo="RODADA_NUMERO_DUPLICADO",
            mensagem="Ja existe uma rodada com este numero para esta modalidade.",
            status_code=409,
        )

    _validar_horario(dto.modo_horario, dto.horario_inicio)

    rodada = Rodada(
        modalidade_id=modalidade.id,
        numero=dto.numero,
        modo_horario=dto.modo_horario,
        horario_inicio=dto.horario_inicio,
        status=RodadaStatus.AGENDADA,
    )
    db.add(rodada)
    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="rodada",
        entidade_id=rodada.id,
        acao="CRIAR",
        antes=None,
        depois=_serializar(rodada),
    )
    return rodada


async def obter_rodada(db: AsyncSession, rodada_id: UUID) -> Rodada:
    rodada = await db.get(Rodada, rodada_id)
    if rodada is None:
        raise AppError(
            codigo="RODADA_NAO_ENCONTRADA", mensagem="Rodada nao encontrada.", status_code=404
        )
    return rodada


async def listar_rodadas(
    db: AsyncSession, *, modalidade_id: UUID | None, page: int, size: int
) -> tuple[list[Rodada], int]:
    stmt = select(Rodada)
    count_stmt = select(func.count()).select_from(Rodada)
    if modalidade_id is not None:
        stmt = stmt.where(Rodada.modalidade_id == modalidade_id)
        count_stmt = count_stmt.where(Rodada.modalidade_id == modalidade_id)

    total = await db.scalar(count_stmt)
    resultado = await db.execute(stmt.order_by(Rodada.numero).offset((page - 1) * size).limit(size))
    itens = list(resultado.scalars().all())
    return itens, total or 0


async def atualizar_rodada(
    db: AsyncSession, rodada_id: UUID, dto: RodadaUpdate, *, usuario_id: UUID
) -> Rodada:
    rodada = await obter_rodada(db, rodada_id)
    antes = _serializar(rodada)

    dados = dto.model_dump(exclude_unset=True)

    _validar_horario(
        dados.get("modo_horario", rodada.modo_horario),
        dados.get("horario_inicio", rodada.horario_inicio),
    )

    for campo, valor in dados.items():
        setattr(rodada, campo, valor)

    await db.flush()

    await registrar_audit_log(
        db,
        usuario_id=usuario_id,
        entidade="rodada",
        entidade_id=rodada.id,
        acao="ATUALIZAR",
        antes=antes,
        depois=_serializar(rodada),
    )
    return rodada


async def gerar_rodadas(db: AsyncSession, modalidade_id: UUID, *, usuario_id: UUID) -> list[Rodada]:
    """Cria as `qtd_rodadas` rodadas vazias de uma modalidade INDIVIDUAL.
    Confronto nao passa por aqui: cada partida (e a rodada dela) e montada na
    mao pelo coordenador em `chaveamento.criar_partida_manual`.
    """
    modalidade = await obter_modalidade(db, modalidade_id)
    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        raise AppError(
            codigo="GERAR_RODADAS_SO_INDIVIDUAL",
            mensagem="Rodadas de combate sao montadas na mao, confronto por confronto.",
            status_code=422,
        )

    existentes_resultado = await db.execute(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id)
    )
    existentes_por_numero = {r.numero: r for r in existentes_resultado.scalars().all()}

    rodadas: list[Rodada] = []
    for numero in range(1, modalidade.qtd_rodadas + 1):
        rodada = existentes_por_numero.get(numero)
        if rodada is None:
            rodada = Rodada(
                modalidade_id=modalidade.id,
                numero=numero,
                modo_horario=ModoHorario.AUTOMATICO,
                horario_inicio=None,
                status=RodadaStatus.AGENDADA,
            )
            db.add(rodada)
            await db.flush()

            await registrar_audit_log(
                db,
                usuario_id=usuario_id,
                entidade="rodada",
                entidade_id=rodada.id,
                acao="CRIAR",
                antes=None,
                depois=_serializar(rodada),
            )

        rodadas.append(rodada)

    return rodadas
