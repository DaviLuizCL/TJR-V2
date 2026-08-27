"""
Script avulso de importacao do cadastro real de equipes (LISTA 2026) -- nao
faz parte do app, roda uma vez (dev pra validar, depois producao) pra criar
as equipes reais e as inscricoes por modalidade a partir da planilha oficial.

Pre-requisito: rodar a seed estrutural primeiro (evento/modalidade/ficha/
arena precisam existir, mas SEM equipe/rodada ficticia -- senao o
chaveamento fake da seed normal bloqueia o real depois, ja que
gerar_chaveamento_confronto recusa iniciar uma modalidade que ja tem
rodada):
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
"""

import asyncio
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import select

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import AsyncSessionLocal
from app.models.equipe import Equipe
from app.models.evento import Evento
from app.models.modalidade import Modalidade
from app.models.usuario import Usuario
from app.schemas.equipe import EquipeCreate
from app.schemas.inscricao import InscricaoCreate
from app.services import equipe as equipe_service
from app.services import inscricao as inscricao_service

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# DESAFIO da planilha -> Modalidade.nome no sistema. "Registro Multimidiatico"
# fica de fora de proposito: nao ha modalidade cadastrada pra ela (unica
# linha da planilha e um placeholder "NAO HA", sem equipe real).
MAPA_MODALIDADE = {
    "Corrida de Carros Autônomos": "Corrida de Carros Autônomos",
    "Resgate de Alto Risco": "Resgate de Alto Risco",
    "Resgate no Plano": "Resgate no Plano",
    "Viagem ao Centro da Terra": "Viagem ao Centro da Terra",
    "Dança de Robôs": "Dança",
    "Sumô RC 1,5 kg": "Sumô RC 1,5 kg",
    "Sumô": "Sumô",
    "Sumô 3 kg": "Sumô 3 kg",
    "Cabo de Guerra": "Cabo de Guerra",
}


def _col_para_indice(referencia: str) -> int:
    letras = "".join(c for c in referencia if c.isalpha())
    indice = 0
    for c in letras:
        indice = indice * 26 + (ord(c.upper()) - ord("A") + 1)
    return indice - 1


def ler_planilha(caminho: Path) -> list[list[str]]:
    arquivo_zip = zipfile.ZipFile(caminho)

    # sharedStrings.xml e opcional -- planilha salva por outra ferramenta
    # (ex.: reaproveitada via openpyxl) pode nao ter nenhuma string
    # compartilhada e omitir o arquivo inteiro, usando inlineStr em vez de
    # referencia por indice.
    compartilhadas: list[str] = []
    if "xl/sharedStrings.xml" in arquivo_zip.namelist():
        raiz_strings = ET.fromstring(arquivo_zip.read("xl/sharedStrings.xml"))
        for item in raiz_strings.findall("m:si", _NS):
            textos = item.findall(".//m:t", _NS)
            compartilhadas.append("".join(t.text or "" for t in textos))

    raiz_planilha = ET.fromstring(arquivo_zip.read("xl/worksheets/sheet1.xml"))
    linhas: list[list[str]] = []
    for linha_xml in raiz_planilha.findall(".//m:sheetData/m:row", _NS):
        dados: dict[int, str] = {}
        for celula in linha_xml.findall("m:c", _NS):
            indice = _col_para_indice(celula.get("r"))
            tipo = celula.get("t")
            if tipo == "inlineStr":
                textos = celula.findall(".//m:is/m:t", _NS)
                valor = "".join(t.text or "" for t in textos)
            else:
                elemento_valor = celula.find("m:v", _NS)
                valor = elemento_valor.text if elemento_valor is not None else ""
                if tipo == "s":
                    valor = compartilhadas[int(valor)] if valor != "" else ""
            dados[indice] = valor
        maior_indice = max(dados.keys()) if dados else -1
        linhas.append([dados.get(i, "") for i in range(maior_indice + 1)])
    return linhas


async def main(caminho_planilha: str) -> None:
    linhas = ler_planilha(Path(caminho_planilha))
    if not linhas:
        print("Planilha vazia.")
        return
    corpo = linhas[1:]  # pula cabecalho

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

        modalidades_por_nome = {
            m.nome: m
            for m in (
                await db.scalars(select(Modalidade).where(Modalidade.evento_id == evento.id))
            ).all()
        }

        equipes_criadas = 0
        inscricoes_criadas = 0
        linhas_ignoradas = 0
        erros: list[str] = []

        for numero_linha, linha in enumerate(corpo, start=2):
            if not linha or not linha[0]:
                continue
            desafio = (linha[0] or "").strip()
            nivel_bruto = (linha[1] or "").strip() if len(linha) > 1 else ""
            nome_equipe = (linha[4] or "").strip() if len(linha) > 4 else ""

            if not desafio or not nome_equipe:
                continue
            if "CONSIDERAR" in nome_equipe.upper():
                linhas_ignoradas += 1
                continue

            modalidade_nome = MAPA_MODALIDADE.get(desafio)
            if modalidade_nome is None:
                linhas_ignoradas += 1
                continue

            modalidade = modalidades_por_nome.get(modalidade_nome)
            if modalidade is None:
                erros.append(
                    f"Linha {numero_linha}: modalidade '{modalidade_nome}' nao existe no sistema."
                )
                continue

            try:
                nivel_planilha = int(nivel_bruto)
            except ValueError:
                erros.append(f"Linha {numero_linha}: nivel invalido '{nivel_bruto}'.")
                continue
            nivel_sistema = 1 if nivel_planilha == 0 else nivel_planilha

            equipe = await db.scalar(
                select(Equipe).where(Equipe.nome == nome_equipe, Equipe.nivel == nivel_sistema)
            )
            if equipe is None:
                try:
                    equipe = await equipe_service.criar_equipe(
                        db,
                        EquipeCreate(nome=nome_equipe, nivel=nivel_sistema),
                        usuario_id=ator.id,
                    )
                except Exception as erro:  # validacao pydantic ou regra de negocio
                    erros.append(
                        f"Linha {numero_linha}: erro criando equipe '{nome_equipe}': {erro}"
                    )
                    continue
                equipes_criadas += 1

            try:
                await inscricao_service.criar_inscricao(
                    db,
                    InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
                    usuario_id=ator.id,
                )
                inscricoes_criadas += 1
            except AppError as erro:
                if erro.codigo != "INSCRICAO_DUPLICADA":
                    erros.append(f"Linha {numero_linha}: {erro.mensagem}")

        await db.commit()

    print(f"Linhas de dado na planilha: {len(corpo)}")
    print(f"Equipes novas criadas: {equipes_criadas}")
    print(f"Inscricoes novas criadas: {inscricoes_criadas}")
    print(f"Linhas ignoradas de proposito (teste/modalidade nao cadastrada): {linhas_ignoradas}")
    if erros:
        print(f"\n{len(erros)} erro(s) -- confira antes de considerar a importacao completa:")
        for erro in erros:
            print(f"  - {erro}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 -m scripts.lista_2026.importar <caminho-da-planilha.xlsx>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
