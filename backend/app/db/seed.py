import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_senha
from app.db.session import AsyncSessionLocal
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.modalidade import (
    Consolidacao,
    FormatoChaveamento,
    Modalidade,
    ModalidadeStatus,
    TipoDisputa,
)
from app.models.usuario import Papel, Usuario

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
    ),
    dict(
        nome="Resgate no Plano",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
    ),
    dict(
        nome="Resgate de Alto Risco",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=1,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
    ),
    dict(
        nome="Viagem ao Centro da Terra",
        tipo_disputa=TipoDisputa.INDIVIDUAL,
        qtd_rodadas=3,
        tentativas_por_rodada=2,
        consolidacao=Consolidacao.IGNORA_MENOR_NOTA,
        ficha_unica_entre_niveis=False,
    ),
)


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
                consolidacao=spec["consolidacao"],
                status=ModalidadeStatus.PUBLICADA,
            )
            db.add(modalidade)
            await db.flush()
        modalidades.append(modalidade)
    return modalidades


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


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_coordenador(
            db, email=settings.seed_coordenador_email, senha=settings.seed_coordenador_senha
        )
        evento = await seed_evento(db)
        await seed_modalidades(db, evento)
        await seed_equipes(db, por_nivel=10)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(_main())
