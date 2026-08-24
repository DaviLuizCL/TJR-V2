"""
Script avulso de credenciamento em lote -- nao faz parte do app, roda uma vez
(dev pra testar, depois producao) pra criar as contas de arbitro/secretaria
a partir de uma lista de emails.

Uso (dentro do container da api):
    docker compose exec -T api python3 -m scripts.credenciamento.importar

Le scripts/credenciamento/entrada.csv (colunas: E-mail,Nome,Função -- "Juiz"
vira ARBITRO, "Admin" vira COORDENADOR) e grava
scripts/credenciamento/saida_credenciais.csv (nome,email,papel,senha) com a
senha em texto puro gerada na hora -- pra voce mandar manualmente por email.
Nao manda email nenhum sozinho, nao tem acesso a nenhum servico de email.

Idempotente: reexecutar o script pula quem ja tem conta (linha sai marcada
"ja existia" na saida, sem mexer na senha antiga).
"""

import asyncio
import csv
import random
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import AsyncSessionLocal
from app.models.usuario import Papel, Usuario
from app.schemas.usuario import UsuarioCreate
from app.services import usuario as usuario_service

MAPA_FUNCAO = {"JUIZ": Papel.ARBITRO, "ADMIN": Papel.COORDENADOR}

PALAVRAS = [
    "frodo", "sam", "merry", "pippin", "gandalf", "aragorn", "legolas",
    "gimli", "boromir", "bilbo", "elrond", "galadriel", "arwen", "eowyn",
    "eomer", "theoden", "faramir", "denethor", "saruman", "sauron", "gollum",
    "smeagol", "shelob", "balrog", "nazgul", "isildur", "elendil", "thorin",
    "bard", "beorn", "radagast", "haldir", "celeborn", "thranduil", "grima",
    "shire", "rivendell", "moria", "gondor", "rohan", "mordor", "isengard",
    "lorien", "fangorn", "ithilien", "osgiliath", "edoras", "bree", "erebor",
    "anduin", "ring", "sting", "anduril", "glamdring", "orcrist", "mithril",
    "palantir", "narsil", "lembas", "elessar", "hobbit", "wizard", "ranger",
    "warg", "eagle", "wraith", "troll", "goblin", "dwarf", "oliphant",
]

DIRETORIO = Path(__file__).parent
ENTRADA = DIRETORIO / "entrada.csv"
SAIDA = DIRETORIO / "saida_credenciais.csv"


def gerar_senha() -> str:
    a, b = random.sample(PALAVRAS, 2)
    return f"{a}.{b}"


def nome_a_partir_do_email(email: str) -> str:
    local = email.split("@")[0]
    partes = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return " ".join(parte.capitalize() for parte in partes) or local


async def main() -> None:
    if not ENTRADA.exists():
        print(f"Nao achei {ENTRADA}. Copie o CSV de entrada (colunas E-mail,Nome,Função) pra entrada.csv.")
        sys.exit(1)

    linhas_saida: list[dict[str, str]] = []

    async with AsyncSessionLocal() as db:
        ator = await db.scalar(
            select(Usuario).where(Usuario.email == settings.seed_coordenador_email)
        )
        if ator is None:
            print(
                "Nao achei o usuario coordenador seed no banco -- "
                "confira SEED_COORDENADOR_EMAIL no .env."
            )
            sys.exit(1)

        with ENTRADA.open(newline="", encoding="utf-8") as arquivo:
            leitor = csv.DictReader(arquivo)
            for linha in leitor:
                email_bruto = (linha.get("E-mail") or "").strip()
                nome_bruto = (linha.get("Nome") or "").strip()
                funcao_bruto = (linha.get("Função") or "").strip()
                if not email_bruto:
                    continue
                email = email_bruto.lower()
                papel = MAPA_FUNCAO.get(funcao_bruto.upper())

                if papel is None:
                    linhas_saida.append(
                        {
                            "nome": nome_bruto,
                            "email": email,
                            "papel": funcao_bruto,
                            "senha": f"ERRO: funcao invalida ({funcao_bruto})",
                        }
                    )
                    continue

                existente = await db.scalar(select(Usuario).where(Usuario.email == email))
                if existente is not None:
                    linhas_saida.append(
                        {
                            "nome": existente.nome,
                            "email": email,
                            "papel": existente.papel.value,
                            "senha": "(ja existia, nao alterada)",
                        }
                    )
                    continue

                senha = gerar_senha()
                nome = nome_bruto or nome_a_partir_do_email(email)
                try:
                    dto = UsuarioCreate(nome=nome, email=email, senha=senha, papel=papel)
                    await usuario_service.criar_usuario(db, dto, usuario_id=ator.id)
                except AppError as erro:
                    linhas_saida.append(
                        {"nome": nome, "email": email, "papel": papel.value, "senha": f"ERRO: {erro.mensagem}"}
                    )
                    continue
                except Exception as erro:  # validacao pydantic (ex.: email invalido)
                    linhas_saida.append(
                        {"nome": nome, "email": email, "papel": papel.value, "senha": f"ERRO: {erro}"}
                    )
                    continue

                linhas_saida.append({"nome": nome, "email": email, "papel": papel.value, "senha": senha})

        await db.commit()

    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["nome", "email", "papel", "senha"])
        escritor.writeheader()
        escritor.writerows(linhas_saida)

    criados = sum(
        1 for linha in linhas_saida if not linha["senha"].startswith(("ERRO", "(ja existia"))
    )
    print(f"{criados} conta(s) nova(s) criada(s) de {len(linhas_saida)} linha(s) processada(s).")
    print(f"Credenciais em: {SAIDA}")


if __name__ == "__main__":
    asyncio.run(main())
