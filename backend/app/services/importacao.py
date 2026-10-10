"""Importacao do cadastro de equipes a partir da planilha oficial (.xlsx).

Antes era so um script de linha de comando (scripts/lista_2026/importar.py);
agora o coordenador sobe a planilha pela tela. O script continua existindo e
chama este servico.

Le a planilha so com biblioteca padrao (zipfile + xml.etree, sem dependencia
nova). Colunas usadas: A = DESAFIO, B = NIVEL, E = nome da EQUIPE. Mapeia o
DESAFIO pro nome real da modalidade (MAPA_MODALIDADE); nivel 0 da planilha vira
nivel 1 (ABSOLUTO); ignora a linha de teste ("... NAO CONSIDERAR") e desafio
sem modalidade no sistema (ex.: "Registro Multimidiatico").

Equipe com o MESMO nome no MESMO nivel e reaproveitada entre modalidades; com o
mesmo nome em nivel diferente vira equipe distinta. Nao apaga nada: importar de
novo so adiciona o que ainda nao existe.
"""

import io
import zipfile
from uuid import UUID
from xml.etree import ElementTree as ET

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.equipe import Equipe
from app.models.modalidade import Modalidade
from app.schemas.equipe import EquipeCreate
from app.schemas.inscricao import InscricaoCreate
from app.services import equipe as equipe_service
from app.services import inscricao as inscricao_service

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# DESAFIO da planilha -> Modalidade.nome no sistema. "Registro Multimidiatico"
# fica de fora de proposito: nao ha modalidade cadastrada pra ela.
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


class RelatorioImportacao(BaseModel):
    simulacao: bool
    linhas: int
    equipes_novas: int
    inscricoes_novas: int
    ignoradas: int
    erros: list[str]


def _col_para_indice(referencia: str) -> int:
    letras = "".join(c for c in referencia if c.isalpha())
    indice = 0
    for c in letras:
        indice = indice * 26 + (ord(c.upper()) - ord("A") + 1)
    return indice - 1


def ler_planilha(conteudo: bytes) -> list[list[str]]:
    try:
        arquivo_zip = zipfile.ZipFile(io.BytesIO(conteudo))
        nomes = arquivo_zip.namelist()
        raiz_planilha = ET.fromstring(arquivo_zip.read("xl/worksheets/sheet1.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as erro:
        raise AppError(
            codigo="PLANILHA_INVALIDA",
            mensagem="O arquivo enviado nao e uma planilha .xlsx valida.",
            status_code=422,
        ) from erro

    # sharedStrings.xml e opcional -- planilha salva por outra ferramenta pode
    # usar inlineStr em vez de referencia por indice.
    compartilhadas: list[str] = []
    if "xl/sharedStrings.xml" in nomes:
        raiz_strings = ET.fromstring(arquivo_zip.read("xl/sharedStrings.xml"))
        for item in raiz_strings.findall("m:si", _NS):
            textos = item.findall(".//m:t", _NS)
            compartilhadas.append("".join(t.text or "" for t in textos))

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


async def _importar_linhas(
    db: AsyncSession, corpo: list[list[str]], *, evento_id: UUID, usuario_id: UUID
) -> tuple[int, int, int, list[str]]:
    modalidades_por_nome = {
        m.nome: m
        for m in (await db.scalars(select(Modalidade).where(Modalidade.evento_id == evento_id)))
    }
    equipes_novas = inscricoes_novas = ignoradas = 0
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
            ignoradas += 1
            continue

        modalidade_nome = MAPA_MODALIDADE.get(desafio)
        if modalidade_nome is None:
            ignoradas += 1
            continue

        modalidade = modalidades_por_nome.get(modalidade_nome)
        if modalidade is None:
            erros.append(
                f"Linha {numero_linha}: modalidade '{modalidade_nome}' nao existe no sistema."
            )
            continue

        try:
            # A planilha pode salvar o nivel como float ("2.0"); int() direto falha.
            nivel_planilha = int(float(nivel_bruto))
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
                    db, EquipeCreate(nome=nome_equipe, nivel=nivel_sistema), usuario_id=usuario_id
                )
            except Exception as erro:  # validacao pydantic ou regra de negocio
                erros.append(f"Linha {numero_linha}: erro criando equipe '{nome_equipe}': {erro}")
                continue
            equipes_novas += 1

        try:
            await inscricao_service.criar_inscricao(
                db,
                InscricaoCreate(equipe_id=equipe.id, modalidade_id=modalidade.id),
                usuario_id=usuario_id,
            )
            inscricoes_novas += 1
        except AppError as erro:
            if erro.codigo != "INSCRICAO_DUPLICADA":
                erros.append(f"Linha {numero_linha}: {erro.mensagem}")

    return equipes_novas, inscricoes_novas, ignoradas, erros


async def importar_planilha(
    db: AsyncSession,
    conteudo: bytes,
    *,
    evento_id: UUID,
    usuario_id: UUID,
    simular: bool,
) -> RelatorioImportacao:
    """Importa a planilha. Com `simular=True` faz tudo dentro de um savepoint e
    desfaz no fim: devolve o relatorio de "o que aconteceria" sem gravar nada."""
    linhas = ler_planilha(conteudo)
    corpo = linhas[1:]  # pula cabecalho

    savepoint = await db.begin_nested()
    try:
        equipes_novas, inscricoes_novas, ignoradas, erros = await _importar_linhas(
            db, corpo, evento_id=evento_id, usuario_id=usuario_id
        )
    except Exception:
        await savepoint.rollback()
        raise
    if simular:
        await savepoint.rollback()
    else:
        await savepoint.commit()

    return RelatorioImportacao(
        simulacao=simular,
        linhas=len(corpo),
        equipes_novas=equipes_novas,
        inscricoes_novas=inscricoes_novas,
        ignoradas=ignoradas,
        erros=erros,
    )
