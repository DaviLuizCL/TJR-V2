import asyncio
from datetime import UTC, date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_senha
from app.db.session import AsyncSessionLocal
from app.models.agendamento import Agendamento
from app.models.arena import Arena
from app.models.criterio import CategoriaCriterio, Criterio, CriterioTipo, ModificadorTipo
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.ficha import Ficha, FichaStatus
from app.models.grupo import Grupo
from app.models.inscricao import Inscricao
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.rodada import Rodada
from app.models.usuario import Papel, Usuario
from app.schemas.arena import ArenaCreate
from app.services import agendamento as agendamento_service
from app.services import arena as arena_service
from app.services import rodada as rodada_service

FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")

MODALIDADES_TJR: tuple[dict, ...] = (
    dict(
        nome="Sumô",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.MATA_MATA,
        qtd_rodadas=5,
        tentativas_por_rodada=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
    ),
    dict(
        nome="Cabo de Guerra",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        qtd_rodadas=5,
        tentativas_por_rodada=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
    ),
    dict(
        nome="Corrida de Carros Autônomos",
        tipo_disputa=TipoDisputa.CONFRONTO,
        formato_chaveamento=FormatoChaveamento.TODOS_CONTRA_TODOS,
        qtd_rodadas=5,
        tentativas_por_rodada=2,
        consolidacao=Consolidacao.SOMA_RODADAS,
    ),
    dict(
        nome="Dança",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        duracao_maxima_rodada_seg=300,
        pausa_entre_rodadas_seg=60,
    ),
    dict(
        nome="Resgate no Plano",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        duracao_maxima_rodada_seg=180,
        pausa_entre_rodadas_seg=30,
    ),
    dict(
        nome="Resgate de Alto Risco",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        duracao_maxima_rodada_seg=180,
        pausa_entre_rodadas_seg=30,
    ),
    dict(
        nome="Viagem ao Centro da Terra",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=2,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        ficha_unica_entre_niveis=False,
        duracao_maxima_rodada_seg=240,
        pausa_entre_rodadas_seg=30,
    ),
)

EQUIPES_TJR: tuple[tuple[str, int], ...] = tuple(
    (f"Nível {nivel} - Equipe {letra}", nivel) for nivel in (1, 2, 3, 4) for letra in "ABCD"
)


def _c(
    nome: str,
    categoria: CategoriaCriterio,
    tipo: CriterioTipo,
    *,
    pontos: float | None = None,
    valores_permitidos: list | None = None,
    max_ocorrencias: int | None = None,
    modificador_tipo: ModificadorTipo | None = None,
    modificador_valor: float | None = None,
) -> dict:
    return dict(
        nome=nome,
        categoria=categoria,
        tipo=tipo,
        pontos=pontos,
        valores_permitidos=valores_permitidos,
        max_ocorrencias=max_ocorrencias,
        modificador_tipo=modificador_tipo,
        modificador_valor=modificador_valor,
    )


_FICHA_RESULTADO_COMBATE: tuple[tuple[str, tuple[dict, ...]], ...] = (
    (
        "Resultado",
        (_c("Venceu o combate", CategoriaCriterio.PONTUACAO, CriterioTipo.BOOLEANO, pontos=1),),
    ),
)

_ESCALA_DANCA = [0, 2, 5, 7, 10]

_FICHA_DANCA: tuple[tuple[str, tuple[dict, ...]], ...] = (
    (
        "Parte Artística",
        (
            _c(
                "Adequação do Figurino",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Desenvolvimento da Temática na Coreografia",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Nível Técnico da Coreografia Conjunta de Humanos e Robôs",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Ousadia dos Movimentos dos Robôs",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Ousadia dos Movimentos dos Humanos",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Adequação da Música",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Sincronia da Música e da Coreografia",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Harmonia da Atuação de Humanos e Robôs",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
        ),
    ),
    (
        "Parte Técnica — Robótica",
        (
            _c(
                "Complexidade de Construção dos Robôs: Eletromecânica",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
            _c(
                "Complexidade de Construção dos Robôs: Programação",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.ESCALA,
                valores_permitidos=_ESCALA_DANCA,
            ),
        ),
    ),
    (
        "Modificadores",
        (
            _c(
                "Paralisação durante o desempenho",
                CategoriaCriterio.PENALIDADE,
                CriterioTipo.MODIFICADOR,
                modificador_tipo=ModificadorTipo.ZERA_TOTAL,
            ),
            _c(
                "Ultrapassou 5 minutos de apresentação",
                CategoriaCriterio.PENALIDADE,
                CriterioTipo.MODIFICADOR,
                modificador_tipo=ModificadorTipo.PERCENTUAL,
                modificador_valor=10,
            ),
        ),
    ),
)

_FICHA_RESGATE_DE_ALTO_RISCO: tuple[tuple[str, tuple[dict, ...]], ...] = (
    (
        "Percurso",
        (
            _c("Pacote de Leite", CategoriaCriterio.PONTUACAO, CriterioTipo.CONTADOR, pontos=10),
            _c("Lombada", CategoriaCriterio.PONTUACAO, CriterioTipo.CONTADOR, pontos=10),
            _c(
                "Superação de Vazio",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.CONTADOR,
                pontos=10,
            ),
            _c(
                "Superação de Rampa Inclinada",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.CONTADOR,
                pontos=50,
            ),
            _c(
                "Alvo Removido e Descartado: Mesmo piso",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=20,
            ),
            _c(
                "Alvo Removido e Descartado: Pisos diferentes",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=50,
            ),
            _c(
                "Finalização com Sucesso",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=50,
            ),
            _c(
                "Objeto lata invertido de posição (ponta cabeça)",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=50,
            ),
            _c(
                "Penalidades (Falha de Progresso)",
                CategoriaCriterio.PENALIDADE,
                CriterioTipo.CONTADOR,
                pontos=0,
            ),
        ),
    ),
)

_FICHA_RESGATE_NO_PLANO: tuple[tuple[str, tuple[dict, ...]], ...] = (
    (
        "Percurso",
        (
            _c("Pacote de Leite", CategoriaCriterio.PONTUACAO, CriterioTipo.CONTADOR, pontos=10),
            _c("Lombada", CategoriaCriterio.PONTUACAO, CriterioTipo.CONTADOR, pontos=10),
            _c(
                "Superação de Vazio",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.CONTADOR,
                pontos=10,
            ),
            _c(
                "Percurso sem falhas antes do objeto alvo",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=50,
            ),
            _c(
                "Percurso sem falhas depois do objeto alvo",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=50,
            ),
            _c(
                "Alvo Removido e Descartado",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=50,
            ),
            _c(
                "Finalização com Sucesso",
                CategoriaCriterio.PONTUACAO,
                CriterioTipo.BOOLEANO,
                pontos=20,
            ),
            _c(
                "Penalidades (Falha de Progresso)",
                CategoriaCriterio.PENALIDADE,
                CriterioTipo.CONTADOR,
                pontos=0,
            ),
        ),
    ),
)


def _ficha_viagem(*, inclui_reinicio: bool) -> tuple[tuple[str, tuple[dict, ...]], ...]:
    criterios: list[dict] = [
        _c(
            "Atingir os 6 Cn sem o alvo, na ida",
            CategoriaCriterio.PONTUACAO,
            CriterioTipo.CONTADOR,
            pontos=6,
            max_ocorrencias=6,
        ),
        _c(
            "Atingir o Cc sem o alvo, na ida",
            CategoriaCriterio.PONTUACAO,
            CriterioTipo.BOOLEANO,
            pontos=4,
        ),
        _c(
            "Capturar o alvo A, em Cc",
            CategoriaCriterio.PONTUACAO,
            CriterioTipo.BOOLEANO,
            pontos=10,
        ),
        _c(
            "Atingir os 6 Cn com o alvo, na volta",
            CategoriaCriterio.PONTUACAO,
            CriterioTipo.CONTADOR,
            pontos=12,
            max_ocorrencias=6,
        ),
        _c(
            "Atingir o Cs com o alvo, na volta",
            CategoriaCriterio.PONTUACAO,
            CriterioTipo.BOOLEANO,
            pontos=8,
        ),
        _c("Soltar o alvo A, em Cs", CategoriaCriterio.PONTUACAO, CriterioTipo.BOOLEANO, pontos=10),
        _c("Atravessar a borda", CategoriaCriterio.PENALIDADE, CriterioTipo.CONTADOR, pontos=5),
    ]
    if inclui_reinicio:
        criterios.append(
            _c(
                "Reinício entre as rodadas",
                CategoriaCriterio.PENALIDADE,
                CriterioTipo.CONTADOR,
                pontos=20,
            )
        )
    return (("Percurso", tuple(criterios)),)


FICHAS_TJR: dict[str, tuple[tuple[str, tuple[dict, ...]], ...]] = {
    "Sumô": _FICHA_RESULTADO_COMBATE,
    "Cabo de Guerra": _FICHA_RESULTADO_COMBATE,
    "Corrida de Carros Autônomos": _FICHA_RESULTADO_COMBATE,
    "Dança": _FICHA_DANCA,
    "Resgate de Alto Risco": _FICHA_RESGATE_DE_ALTO_RISCO,
    "Resgate no Plano": _FICHA_RESGATE_NO_PLANO,
}

FICHA_VIAGEM_POR_NIVEL: dict[int, tuple[tuple[str, tuple[dict, ...]], ...]] = {
    1: _ficha_viagem(inclui_reinicio=False),
    2: _ficha_viagem(inclui_reinicio=False),
    3: _ficha_viagem(inclui_reinicio=True),
    4: _ficha_viagem(inclui_reinicio=True),
}


async def seed_coordenador(db: AsyncSession, *, email: str, senha: str) -> Usuario:
    resultado = await db.execute(select(Usuario).where(Usuario.email == email))
    usuario = resultado.scalar_one_or_none()
    if usuario is not None:
        return usuario

    usuario = Usuario(
        nome="Coordenador",
        email=email,
        senha_hash=hash_senha(senha),
        papel=Papel.COORDENADOR,
        ativo=True,
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def seed_evento(
    db: AsyncSession,
    *,
    nome: str = "TJR 2026",
    ano: int = 2026,
    data_inicio: date = date(2026, 3, 10),
    data_fim: date = date(2026, 3, 12),
) -> Evento:
    resultado = await db.execute(select(Evento).where(Evento.nome == nome))
    evento = resultado.scalar_one_or_none()
    if evento is not None:
        return evento

    evento = Evento(
        nome=nome,
        ano=ano,
        data_inicio=data_inicio,
        data_fim=data_fim,
        status=EventoStatus.RASCUNHO,
    )
    db.add(evento)
    await db.flush()
    return evento


async def seed_modalidades(db: AsyncSession, evento: Evento) -> list[Modalidade]:
    modalidades: list[Modalidade] = []
    for spec in MODALIDADES_TJR:
        resultado = await db.execute(
            select(Modalidade).where(
                Modalidade.evento_id == evento.id, Modalidade.nome == spec["nome"]
            )
        )
        modalidade = resultado.scalar_one_or_none()
        if modalidade is None:
            modalidade = Modalidade(
                evento_id=evento.id,
                nome=spec["nome"],
                tipo_disputa=spec["tipo_disputa"],
                formato_chaveamento=spec.get("formato_chaveamento"),
                niveis_aplicaveis=[1, 2, 3, 4],
                ficha_unica_entre_niveis=spec.get("ficha_unica_entre_niveis", True),
                qtd_rodadas=spec["qtd_rodadas"],
                tentativas_por_rodada=spec["tentativas_por_rodada"],
                duracao_maxima_rodada_seg=spec.get("duracao_maxima_rodada_seg"),
                pausa_entre_rodadas_seg=spec.get("pausa_entre_rodadas_seg"),
                consolidacao=spec["consolidacao"],
                status=ModalidadeStatus.PUBLICADA,
            )
            db.add(modalidade)
            await db.flush()
        modalidades.append(modalidade)
    return modalidades


async def _obter_ou_criar_ficha(
    db: AsyncSession,
    *,
    modalidade_id,
    nivel: int | None,
    grupos_spec: tuple[tuple[str, tuple[dict, ...]], ...],
) -> Ficha:
    resultado = await db.execute(
        select(Ficha).where(Ficha.modalidade_id == modalidade_id, Ficha.nivel == nivel)
    )
    ficha = resultado.scalar_one_or_none()
    if ficha is not None:
        return ficha

    ficha = Ficha(
        modalidade_id=modalidade_id,
        nivel=nivel,
        versao=1,
        status=FichaStatus.PUBLICADA,
        publicada_em=datetime.now(UTC),
    )
    db.add(ficha)
    await db.flush()

    for grupo_ordem, (nome_grupo, criterios) in enumerate(grupos_spec, start=1):
        grupo = Grupo(ficha_id=ficha.id, nome=nome_grupo, ordem=grupo_ordem)
        db.add(grupo)
        await db.flush()

        for criterio_ordem, spec in enumerate(criterios, start=1):
            db.add(
                Criterio(
                    grupo_id=grupo.id,
                    nome=spec["nome"],
                    categoria=spec["categoria"],
                    tipo=spec["tipo"],
                    pontos=spec["pontos"],
                    valores_permitidos=spec["valores_permitidos"],
                    max_ocorrencias=spec["max_ocorrencias"],
                    modificador_tipo=spec["modificador_tipo"],
                    modificador_valor=spec["modificador_valor"],
                    ordem=criterio_ordem,
                )
            )
        await db.flush()

    return ficha


async def seed_fichas(db: AsyncSession, modalidades: list[Modalidade]) -> list[Ficha]:
    fichas: list[Ficha] = []
    for modalidade in modalidades:
        if modalidade.nome in FICHAS_TJR:
            fichas.append(
                await _obter_ou_criar_ficha(
                    db,
                    modalidade_id=modalidade.id,
                    nivel=None,
                    grupos_spec=FICHAS_TJR[modalidade.nome],
                )
            )
        elif modalidade.nome == "Viagem ao Centro da Terra":
            for nivel, grupos_spec in FICHA_VIAGEM_POR_NIVEL.items():
                fichas.append(
                    await _obter_ou_criar_ficha(
                        db, modalidade_id=modalidade.id, nivel=nivel, grupos_spec=grupos_spec
                    )
                )
    return fichas


async def seed_equipes(db: AsyncSession, *, por_nivel: int = 10) -> list[Equipe]:
    equipes: list[Equipe] = []
    for nivel in (1, 2, 3, 4):
        for numero in range(1, por_nivel + 1):
            nome = f"Equipe {numero:02d} - Nivel {nivel}"
            resultado = await db.execute(select(Equipe).where(Equipe.nome == nome))
            equipe = resultado.scalar_one_or_none()
            if equipe is None:
                equipe = Equipe(nome=nome, nivel=nivel, ativo=True)
                db.add(equipe)
                await db.flush()
            equipes.append(equipe)
    return equipes


async def seed_equipes_credenciadas(db: AsyncSession) -> list[Equipe]:
    equipes: list[Equipe] = []
    for nome, nivel in EQUIPES_TJR:
        resultado = await db.execute(select(Equipe).where(Equipe.nome == nome))
        equipe = resultado.scalar_one_or_none()
        if equipe is None:
            equipe = Equipe(nome=nome, nivel=nivel, ativo=True)
            db.add(equipe)
            await db.flush()
        equipes.append(equipe)
    return equipes


async def seed_inscricoes(
    db: AsyncSession, modalidades: list[Modalidade], equipes: list[Equipe]
) -> list[Inscricao]:
    inscricoes: list[Inscricao] = []
    for modalidade in modalidades:
        for equipe in equipes:
            if equipe.nivel not in modalidade.niveis_aplicaveis:
                continue

            resultado = await db.execute(
                select(Inscricao).where(
                    Inscricao.equipe_id == equipe.id, Inscricao.modalidade_id == modalidade.id
                )
            )
            inscricao = resultado.scalar_one_or_none()
            if inscricao is None:
                inscricao = Inscricao(equipe_id=equipe.id, modalidade_id=modalidade.id)
                db.add(inscricao)
                await db.flush()
            inscricoes.append(inscricao)
    return inscricoes


async def seed_arenas(
    db: AsyncSession, modalidades: list[Modalidade], *, usuario_id: UUID
) -> list[Arena]:
    arenas: list[Arena] = []
    for modalidade in modalidades:
        if modalidade.tipo_disputa != TipoDisputa.INDIVIDUAL:
            continue

        resultado = await db.execute(select(Arena).where(Arena.modalidade_id == modalidade.id))
        existentes = list(resultado.scalars().all())
        if existentes:
            arenas.extend(existentes)
            continue

        arena = await arena_service.criar_arena(
            db,
            ArenaCreate(
                modalidade_id=modalidade.id,
                nome=f"Arena {modalidade.nome}",
                niveis_aplicaveis=None,
                ativo=True,
            ),
            usuario_id=usuario_id,
        )
        arenas.append(arena)
    return arenas


async def seed_rodadas(
    db: AsyncSession, modalidades: list[Modalidade], *, usuario_id: UUID
) -> list[Rodada]:
    rodadas: list[Rodada] = []
    for modalidade in modalidades:
        rodadas.extend(
            await rodada_service.gerar_rodadas(db, modalidade.id, usuario_id=usuario_id)
        )
    return rodadas


def _horario_inicio_padrao(evento: Evento) -> datetime:
    inicio_local = datetime.combine(evento.data_inicio, time(8, 0), tzinfo=FUSO_FORTALEZA)
    return inicio_local.astimezone(UTC)


async def seed_agendamentos(
    db: AsyncSession, evento: Evento, modalidades: list[Modalidade], *, usuario_id: UUID
) -> list[Agendamento]:
    agendamentos: list[Agendamento] = []
    horario_inicio = _horario_inicio_padrao(evento)

    for modalidade in modalidades:
        if modalidade.tipo_disputa != TipoDisputa.INDIVIDUAL:
            continue

        resultado_existentes = await db.execute(
            select(Agendamento)
            .join(Rodada, Agendamento.rodada_id == Rodada.id)
            .where(Rodada.modalidade_id == modalidade.id)
        )
        existentes = list(resultado_existentes.scalars().all())
        if existentes:
            agendamentos.extend(existentes)
            continue

        resultado_rodadas = await db.execute(
            select(Rodada.id)
            .where(Rodada.modalidade_id == modalidade.id)
            .order_by(Rodada.numero)
        )
        rodada_ids = [row[0] for row in resultado_rodadas.all()]
        if not rodada_ids:
            continue

        novos = await agendamento_service.gerar_agendamentos(
            db,
            modalidade.id,
            rodada_ids,
            horario_inicio,
            usuario_id=usuario_id,
        )
        agendamentos.extend(novos)

    return agendamentos


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        coordenador = await seed_coordenador(
            db, email=settings.seed_coordenador_email, senha=settings.seed_coordenador_senha
        )
        evento = await seed_evento(db)
        modalidades = await seed_modalidades(db, evento)
        await seed_fichas(db, modalidades)
        equipes = await seed_equipes_credenciadas(db)
        await seed_inscricoes(db, modalidades, equipes)
        await seed_arenas(db, modalidades, usuario_id=coordenador.id)
        await seed_rodadas(db, modalidades, usuario_id=coordenador.id)
        await seed_agendamentos(db, evento, modalidades, usuario_id=coordenador.id)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(_main())
