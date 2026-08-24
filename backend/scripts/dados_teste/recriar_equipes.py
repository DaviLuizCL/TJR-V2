"""
Script avulso -- nao faz parte do app. Zera os dados de competicao (equipe,
inscricao, rodada, partida, agendamento, lancamento, lancamento_item) e recria
equipes ficticias com nome tematico (Harry Potter / Senhor dos Aneis), 15-20
por nivel de cada modalidade, ja inscritas -- pra comecar a pontuar do zero e
conferir relatorio/chaveamento com volume real de dado.

Excecao deliberada a regra invioravel 5 (nada de DELETE em dado de
pontuacao): pedido explicito do usuario pra "comecar a competicao do 0",
mesma categoria de reset completo ja feito antes neste projeto. Nao mantem
audit_log da limpeza (seria centenas de linhas pra um reset de ambiente de
teste, nao uma correcao pontual) -- so a criacao das equipes/inscricoes novas
passa pelo audit log de sempre.

Uso (dentro do container da api):
    docker compose exec -T api python3 -m scripts.dados_teste.recriar_equipes

Nao mexe em usuario, evento, modalidade, ficha/criterio ou arena.
"""

import asyncio
import random

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.agendamento import Agendamento
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.lancamento import Lancamento
from app.models.lancamento_item import LancamentoItem
from app.models.modalidade import Modalidade
from app.models.partida import Partida
from app.models.rodada import Rodada
from app.models.usuario import Usuario
from app.schemas.equipe import EquipeCreate
from app.schemas.inscricao import InscricaoCreate
from app.services.equipe import criar_equipe
from app.services.inscricao import criar_inscricao

SIGLAS_MODALIDADE = {
    "Sumô": "SUM",
    "Cabo de Guerra": "CDG",
    "Corrida de Carros Autônomos": "CCA",
    "Dança": "DAN",
    "Resgate no Plano": "RNP",
    "Resgate de Alto Risco": "RAR",
    "Viagem ao Centro da Terra": "VCT",
}

EQUIPES_POR_GRUPO = (15, 20)  # min, max inclusive

NOMES_POTTER = [
    "Harry", "Ron", "Hermione", "Neville", "Luna", "Ginny", "Fred", "George",
    "Percy", "Draco", "Snape", "Dumbledore", "Hagrid", "Sirius", "Lupin",
    "Tonks", "Moody", "Voldemort", "Bellatrix", "Lucius", "Narcissa",
    "Cedric", "Fleur", "Krum", "Dobby", "Hedwig", "Fawkes", "Nagini",
    "Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw", "Hogwarts",
    "Azkaban", "Gringotts", "Patronus", "Basilisk", "Thestral", "Niffler",
    "Buckbeak", "Fluffy", "Scabbers", "Crookshanks", "Firebolt", "Snitch",
    "Galleon", "Umbridge", "Slughorn", "Trelawney", "Flitwick", "Sprout",
    "Filch", "Myrtle", "Peeves", "Griphook", "Kreacher", "Winky", "Dementor",
    "Auror", "Muggle", "Quaffle", "Bludger", "Mandrake", "Boggart",
    "Hippogriff", "Phoenix",
]

NOMES_ANEIS = [
    "Frodo", "Sam", "Merry", "Pippin", "Gandalf", "Aragorn", "Legolas",
    "Gimli", "Boromir", "Bilbo", "Elrond", "Galadriel", "Arwen", "Eowyn",
    "Eomer", "Theoden", "Faramir", "Denethor", "Saruman", "Sauron",
    "Gollum", "Smeagol", "Shelob", "Balrog", "Nazgul", "Isildur", "Elendil",
    "Thorin", "Bard", "Beorn", "Radagast", "Haldir", "Celeborn",
    "Thranduil", "Grima", "Shire", "Rivendell", "Moria", "Gondor", "Rohan",
    "Mordor", "Isengard", "Lorien", "Fangorn", "Ithilien", "Osgiliath",
    "Edoras", "Bree", "Erebor", "Anduin", "Sting", "Anduril", "Glamdring",
    "Orcrist", "Mithril", "Palantir", "Narsil", "Lembas", "Elessar",
    "Hobbit", "Wizard", "Ranger", "Warg", "Eagle", "Wraith", "Troll",
    "Goblin", "Dwarf", "Oliphant",
]

BANCOS_NOMES = (("POTTER", NOMES_POTTER), ("ANEIS", NOMES_ANEIS))


def gerar_nome(usados: set[str], nivel: int, sigla: str) -> str:
    while True:
        franquia, banco = random.choice(BANCOS_NOMES)
        base = random.choice(banco)
        nome = f"{base} - {franquia} - NV{nivel} - {sigla}"
        if nome not in usados:
            usados.add(nome)
            return nome


async def main() -> None:
    async with AsyncSessionLocal() as db:
        ator = await db.scalar(
            select(Usuario).where(Usuario.email == settings.seed_coordenador_email)
        )
        if ator is None:
            print(
                "Nao achei o usuario coordenador seed no banco -- "
                "confira SEED_COORDENADOR_EMAIL no .env."
            )
            return

        for modelo in (LancamentoItem, Lancamento, Partida, Agendamento, Rodada, Inscricao, Equipe):
            await db.execute(delete(modelo))
        await db.flush()

        modalidades = (await db.execute(select(Modalidade))).scalars().all()

        total_equipes = 0
        for modalidade in sorted(modalidades, key=lambda m: m.nome):
            sigla = SIGLAS_MODALIDADE.get(modalidade.nome, modalidade.nome[:3].upper())
            for nivel in sorted(modalidade.niveis_aplicaveis):
                qtd = random.randint(*EQUIPES_POR_GRUPO)
                usados: set[str] = set()
                for _ in range(qtd):
                    nome = gerar_nome(usados, nivel, sigla)
                    equipe = await criar_equipe(
                        db, EquipeCreate(nome=nome, nivel=nivel, ativo=True), usuario_id=ator.id
                    )
                    await criar_inscricao(
                        db,
                        InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
                        usuario_id=ator.id,
                    )
                    total_equipes += 1
                print(f"{modalidade.nome} - NV{nivel}: {qtd} equipes")

        await db.commit()
        print(f"\nTotal: {total_equipes} equipes criadas e inscritas.")


if __name__ == "__main__":
    asyncio.run(main())
