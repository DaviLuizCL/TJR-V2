from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.modalidade import FormatoChaveamento, TipoDisputa
from app.models.partida import Partida, PartidaStatus
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


def _gerar_pareamento(equipe_ids: list[UUID], rodada_numero: int) -> list[tuple[UUID, UUID]]:
    """Pareamento round-robin (metodo do circulo): fixa a primeira equipe e
    roda o restante a cada rodada, para so repetir pares quando qtd_rodadas
    exceder o numero de equipes - 1. Numero impar de equipes deixa uma de bye.
    Isso e so pareamento simples; mata-mata (chaveamento de fato) fica para a
    Fase 4.
    """
    times: list[UUID | None] = list(equipe_ids)
    if len(times) % 2 == 1:
        times.append(None)

    n = len(times)
    if n < 2:
        return []

    fixo = times[0]
    resto = times[1:]
    deslocamento = (rodada_numero - 1) % len(resto)
    resto_rotacionado = resto[deslocamento:] + resto[:deslocamento]
    ordenados = [fixo, *resto_rotacionado]

    pares = []
    for i in range(n // 2):
        a = ordenados[i]
        b = ordenados[n - 1 - i]
        if a is not None and b is not None:
            pares.append((a, b))
    return pares


def _rodadas_necessarias(qtd_equipes: int) -> int:
    """Quantas rodadas o metodo do circulo consegue gerar sem repetir par pra
    um grupo de `qtd_equipes` equipes (numero impar ganha um bye, que conta
    como padding par pro calculo).
    """
    return qtd_equipes - 1 if qtd_equipes % 2 == 0 else qtd_equipes


async def gerar_rodadas(db: AsyncSession, modalidade_id: UUID, *, usuario_id: UUID) -> list[Rodada]:
    """Equipes de niveis diferentes nunca se enfrentam: cada nivel roda seu
    proprio returno (metodo do circulo) dentro da mesma modalidade. Um nivel
    com menos equipes esgota seus confrontos possiveis mais cedo e para de
    receber partida nas rodadas finais, evitando repetir jogo.
    """
    modalidade = await obter_modalidade(db, modalidade_id)

    existentes_resultado = await db.execute(
        select(Rodada).where(Rodada.modalidade_id == modalidade.id)
    )
    existentes_por_numero = {r.numero: r for r in existentes_resultado.scalars().all()}

    equipes_por_nivel: dict[int, list[UUID]] = {}
    if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
        resultado_insc = await db.execute(
            select(Inscricao.equipe_id, Equipe.nivel)
            .join(Equipe, Inscricao.equipe_id == Equipe.id)
            .where(Inscricao.modalidade_id == modalidade.id)
            .order_by(Inscricao.equipe_id)
        )
        for equipe_id, nivel in resultado_insc.all():
            equipes_por_nivel.setdefault(nivel, []).append(equipe_id)

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

        if modalidade.tipo_disputa == TipoDisputa.CONFRONTO:
            qtd_partidas_existentes = await db.scalar(
                select(func.count()).select_from(Partida).where(Partida.rodada_id == rodada.id)
            )
            if not qtd_partidas_existentes:
                for nivel, equipe_ids in equipes_por_nivel.items():
                    if numero > _rodadas_necessarias(len(equipe_ids)):
                        continue
                    for equipe_a_id, equipe_b_id in _gerar_pareamento(equipe_ids, numero):
                        db.add(
                            Partida(
                                rodada_id=rodada.id,
                                equipe_a_id=equipe_a_id,
                                equipe_b_id=equipe_b_id,
                                nivel=nivel,
                                formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
                                status=PartidaStatus.AGENDADA,
                            )
                        )
                await db.flush()

    return rodadas
