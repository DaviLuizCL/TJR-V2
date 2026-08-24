"""
Script avulso -- ajuste pontual pra garantir numero impar de equipes em cada
nivel do Sumo (MATA_MATA), pra exercitar de proposito a regra do bye
resolvido rodada a rodada (secao 6 do CLAUDE.md) numa rodada de teste de
usabilidade. Roda depois de scripts/dados_teste/recriar_equipes.py.

Uso: docker compose exec -T api python3 -m scripts.dados_teste.forcar_impar_sumo
"""

import asyncio
import random

from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.equipe import Equipe
from app.models.inscricao import Inscricao
from app.models.modalidade import Modalidade
from app.models.usuario import Usuario
from app.schemas.equipe import EquipeCreate
from app.schemas.inscricao import InscricaoCreate
from app.services.equipe import criar_equipe
from app.services.inscricao import criar_inscricao

from scripts.dados_teste.recriar_equipes import BANCOS_NOMES, SIGLAS_MODALIDADE


async def main() -> None:
    async with AsyncSessionLocal() as db:
        ator = await db.scalar(
            select(Usuario).where(Usuario.email == settings.seed_coordenador_email)
        )
        if ator is None:
            print("Nao achei o coordenador seed.")
            return

        modalidade = await db.scalar(select(Modalidade).where(Modalidade.nome == "Sumô"))
        if modalidade is None:
            print("Nao achei a modalidade Sumô.")
            return
        sigla = SIGLAS_MODALIDADE["Sumô"]

        for nivel in sorted(modalidade.niveis_aplicaveis):
            total = await db.scalar(
                select(func.count())
                .select_from(Inscricao)
                .join(Equipe, Equipe.id == Inscricao.equipe_id)
                .where(Inscricao.modalidade_id == modalidade.id, Equipe.nivel == nivel)
            )

            if total % 2 == 1:
                print(f"Sumô NV{nivel}: {total} (ja impar, nada a fazer)")
                continue

            franquia, banco = random.choice(BANCOS_NOMES)
            nome = f"{random.choice(banco)}Extra - {franquia} - NV{nivel} - {sigla}"
            equipe = await criar_equipe(
                db, EquipeCreate(nome=nome, nivel=nivel, ativo=True), usuario_id=ator.id
            )
            await criar_inscricao(
                db,
                InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
                usuario_id=ator.id,
            )
            print(f"Sumô NV{nivel}: {total} -> {total + 1} (adicionado {nome})")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
