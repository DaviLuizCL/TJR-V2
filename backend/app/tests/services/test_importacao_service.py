import io
import zipfile
from datetime import date
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.core.security import hash_senha
from app.models.equipe import Equipe
from app.models.evento import Evento, EventoStatus
from app.models.inscricao import Inscricao
from app.models.modalidade import Consolidacao, Modalidade, ModalidadeStatus, TipoDisputa
from app.models.usuario import Papel, Usuario
from app.services.importacao import importar_planilha

CABECALHO = ["DESAFIO", "NIVEL", "ESCOLA", "MENTOR", "EQUIPE"]


def _xlsx(linhas: list[list[str]]) -> bytes:
    """Monta um .xlsx minimo (so sheet1, celulas inlineStr) igual ao que o
    leitor da planilha oficial entende."""
    linhas_xml = []
    for i, linha in enumerate(linhas, start=1):
        celulas = "".join(
            f'<c r="{chr(ord("A") + j)}{i}" t="inlineStr"><is><t>{escape(valor)}</t></is></c>'
            for j, valor in enumerate(linha)
        )
        linhas_xml.append(f'<row r="{i}">{celulas}</row>')
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(linhas_xml)}</sheetData></worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo:
        arquivo.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


async def _cenario(db):
    coordenador = Usuario(
        nome="Coord",
        email="coord-import@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    evento = Evento(
        nome="TJR",
        ano=2026,
        data_inicio=date(2026, 3, 10),
        data_fim=date(2026, 3, 12),
        status=EventoStatus.RASCUNHO,
    )
    db.add_all([coordenador, evento])
    await db.flush()
    for nome in ("Dança", "Sumô"):
        db.add(
            Modalidade(
                evento_id=evento.id,
                nome=nome,
                tipo_disputa=TipoDisputa.INDIVIDUAL,
                niveis_aplicaveis=[1, 2, 3, 4],
                ficha_unica_entre_niveis=False,
                qtd_rodadas=2,
                consolidacao=Consolidacao.SOMA_RODADAS,
                status=ModalidadeStatus.RASCUNHO,
            )
        )
    await db.flush()
    return coordenador, evento


async def _contar(db, model):
    return await db.scalar(select(func.count()).select_from(model))


async def test_importar_cria_equipes_e_inscricoes(db_session):
    coordenador, evento = await _cenario(db_session)
    planilha = _xlsx(
        [
            CABECALHO,
            ["Dança de Robôs", "2", "Escola X", "Ana", "Robotech"],
            ["Sumô", "2", "Escola X", "Ana", "Robotech"],
            ["Sumô", "3", "Escola Y", "Bia", "Megabots"],
        ]
    )

    relatorio = await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=False
    )

    assert relatorio.equipes_novas == 2
    assert relatorio.inscricoes_novas == 3
    assert relatorio.erros == []
    assert await _contar(db_session, Equipe) == 2


async def test_importar_nivel_0_vira_nivel_1(db_session):
    coordenador, evento = await _cenario(db_session)
    planilha = _xlsx([CABECALHO, ["Sumô", "0.0", "E", "M", "Absolutos"]])

    await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=False
    )

    equipe = await db_session.scalar(select(Equipe).where(Equipe.nome == "Absolutos"))
    assert equipe.nivel == 1


async def test_importar_em_modo_simulacao_nao_grava_nada(db_session):
    coordenador, evento = await _cenario(db_session)
    planilha = _xlsx([CABECALHO, ["Sumô", "2", "E", "M", "Robotech"]])

    relatorio = await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=True
    )

    assert relatorio.equipes_novas == 1
    assert relatorio.inscricoes_novas == 1
    assert await _contar(db_session, Equipe) == 0
    assert await _contar(db_session, Inscricao) == 0


async def test_importar_de_novo_nao_duplica(db_session):
    coordenador, evento = await _cenario(db_session)
    planilha = _xlsx([CABECALHO, ["Sumô", "2", "E", "M", "Robotech"]])
    await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=False
    )

    relatorio = await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=False
    )

    assert relatorio.equipes_novas == 0
    assert relatorio.inscricoes_novas == 0
    assert await _contar(db_session, Equipe) == 1


async def test_importar_ignora_linha_de_teste_e_desafio_desconhecido(db_session):
    coordenador, evento = await _cenario(db_session)
    planilha = _xlsx(
        [
            CABECALHO,
            ["Sumô", "2", "E", "M", "TESTE - NAO CONSIDERAR"],
            ["Registro Multimidiático", "2", "E", "M", "Fulanos"],
        ]
    )

    relatorio = await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=False
    )

    assert relatorio.ignoradas == 2
    assert relatorio.equipes_novas == 0


async def test_importar_relata_erro_por_linha_sem_parar_as_outras(db_session):
    coordenador, evento = await _cenario(db_session)
    planilha = _xlsx(
        [
            CABECALHO,
            ["Sumô", "abc", "E", "M", "Nivel Ruim"],
            ["Cabo de Guerra", "2", "E", "M", "Sem Modalidade"],
            ["Sumô", "2", "E", "M", "Boa"],
        ]
    )

    relatorio = await importar_planilha(
        db_session, planilha, evento_id=evento.id, usuario_id=coordenador.id, simular=False
    )

    assert relatorio.equipes_novas == 1
    assert len(relatorio.erros) == 2
    assert relatorio.erros[0].startswith("Linha 2:")
    assert "Cabo de Guerra" in relatorio.erros[1]


async def test_importar_arquivo_que_nao_e_planilha_e_recusado(db_session):
    coordenador, evento = await _cenario(db_session)

    with pytest.raises(AppError) as erro:
        await importar_planilha(
            db_session,
            b"isto nao e um xlsx",
            evento_id=evento.id,
            usuario_id=coordenador.id,
            simular=True,
        )
    assert erro.value.codigo == "PLANILHA_INVALIDA"
