"""
Script avulso de importacao do cadastro real de equipes (LISTA 2026) -- nao
faz parte do app, roda uma vez (dev pra validar, depois producao) pra criar
as equipes reais e as inscricoes por modalidade a partir da planilha oficial.

Pre-requisito: rodar a seed estrutural primeiro (evento/modalidade/ficha/
arena precisam existir, mas SEM equipe/rodada ficticia -- senao equipe e
rodada fake da seed normal se misturam com o cadastro real):
    docker compose exec -T api python3 -m app.db.seed --apenas-estrutura

Uso (dentro do container da api, apontando pra planilha no volume montado):
    docker compose exec -T api python3 -m scripts.lista_2026.importar \
        "/app/scripts/lista_2026/LISTA 2026.xlsx"

Le a planilha direto, so com biblioteca padrao (zipfile + xml.etree, sem
dependencia nova). Mapeia a coluna DESAFIO pro nome real da modalidade no
sistema (MAPA_MODALIDADE), nivel 0 da planilha vira nivel 1 no sistema
(ABSOLUTO, so o rotulo muda -- ver lib/nivel.ts no front), ignora a linha de
teste ("TESTE - NAO CONSIDERAR", Cabo de Guerra Nivel 3) e a modalidade
"Registro Multimidiatico" (nao cadastrada no sistema, unica linha e um
placeholder "NAO HA").

Equipe com o MESMO nome em niveis DIFERENTES vira equipe distinta (decisao
tomada com o coordenador -- ex.: "SESC I" aparece cadastrada em nivel 2 e
nivel 3 na planilha; pode ser 2 times de verdade ou erro de digitacao, fica
pra ele corrigir manualmente depois se for o caso). Equipe com o MESMO nome
no MESMO nivel e reaproveitada entre modalidades -- idempotente a
reexecucao do script, e cobre o caso normal de uma equipe que compete em
mais de uma modalidade do seu nivel.

Nao apaga nada. Rodar de novo so adiciona o que ainda nao existe (equipe
identica por nome+nivel, inscricao identica por equipe+modalidade).

A logica de leitura/importacao mora em app/services/importacao.py (a mesma que
a tela "Importar equipes" do painel de Administracao usa). Este script so
chama o servico com o coordenador seed como autor.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.evento import Evento
from app.models.usuario import Usuario
from app.services.importacao import importar_planilha


async def main(caminho_planilha: str) -> None:
    conteudo = Path(caminho_planilha).read_bytes()

    async with AsyncSessionLocal() as db:
        evento = await db.scalar(select(Evento))
        if evento is None:
            print("Nenhum evento encontrado -- rode a seed estrutural primeiro:")
            print("  python3 -m app.db.seed --apenas-estrutura")
            sys.exit(1)

        ator = await db.scalar(
            select(Usuario).where(Usuario.email == settings.seed_coordenador_email)
        )
        if ator is None:
            print("Nao achei o usuario coordenador seed -- confira SEED_COORDENADOR_EMAIL no .env.")
            sys.exit(1)

        relatorio = await importar_planilha(
            db, conteudo, evento_id=evento.id, usuario_id=ator.id, simular=False
        )
        await db.commit()

    print(f"Linhas de dado na planilha: {relatorio.linhas}")
    print(f"Equipes novas criadas: {relatorio.equipes_novas}")
    print(f"Inscricoes novas criadas: {relatorio.inscricoes_novas}")
    print(f"Linhas ignoradas de proposito (teste/modalidade nao cadastrada): {relatorio.ignoradas}")
    if relatorio.erros:
        qtd = len(relatorio.erros)
        print(f"\n{qtd} erro(s) -- confira antes de considerar a importacao completa:")
        for erro in relatorio.erros:
            print(f"  - {erro}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 -m scripts.lista_2026.importar <caminho-da-planilha.xlsx>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
