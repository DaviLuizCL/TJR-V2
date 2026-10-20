import uuid

import pytest

from app.core.errors import AppError
from app.models.regra_modalidade import TipoRegra
from app.services.regra_modalidade import (
    TAMANHO_MAXIMO_BYTES,
    enviar_regra,
    listar_regras_do_evento,
    obter_regra,
    remover_regra,
)
from app.tests.services.test_checklist_service import _arbitro, _evento, _modalidade

PDF = b"%PDF-1.4\n%conteudo de teste\n%%EOF"


async def test_enviar_regra_guarda_o_pdf_da_modalidade(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    usuario = await _arbitro(db_session, "coord-regra-1@tjr.app")

    await enviar_regra(
        db_session,
        modalidade.id,
        TipoRegra.MANUAL,
        nome_arquivo="manual.pdf",
        conteudo=PDF,
        usuario_id=usuario.id,
    )

    regra = await obter_regra(db_session, modalidade.id, TipoRegra.MANUAL)
    assert regra.conteudo == PDF
    assert regra.nome_arquivo == "manual.pdf"


async def test_enviar_regra_de_novo_substitui_o_pdf_anterior(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    usuario = await _arbitro(db_session, "coord-regra-2@tjr.app")
    novo = PDF + b"\n%versao 2"

    for nome, conteudo in [("v1.pdf", PDF), ("v2.pdf", novo)]:
        await enviar_regra(
            db_session,
            modalidade.id,
            TipoRegra.CADERNO_ALUNO,
            nome_arquivo=nome,
            conteudo=conteudo,
            usuario_id=usuario.id,
        )

    regra = await obter_regra(db_session, modalidade.id, TipoRegra.CADERNO_ALUNO)
    assert regra.conteudo == novo
    assert regra.nome_arquivo == "v2.pdf"


async def test_manual_e_caderno_do_aluno_sao_independentes(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    usuario = await _arbitro(db_session, "coord-regra-3@tjr.app")

    await enviar_regra(
        db_session,
        modalidade.id,
        TipoRegra.MANUAL,
        nome_arquivo="manual.pdf",
        conteudo=PDF,
        usuario_id=usuario.id,
    )

    with pytest.raises(AppError) as erro:
        await obter_regra(db_session, modalidade.id, TipoRegra.CADERNO_ALUNO)
    assert erro.value.codigo == "REGRA_NAO_ENCONTRADA"
    assert erro.value.status_code == 404


async def test_enviar_regra_recusa_arquivo_que_nao_e_pdf(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    usuario = await _arbitro(db_session, "coord-regra-4@tjr.app")

    with pytest.raises(AppError) as erro:
        await enviar_regra(
            db_session,
            modalidade.id,
            TipoRegra.MANUAL,
            nome_arquivo="manual.docx",
            conteudo=b"PK\x03\x04 nao e pdf",
            usuario_id=usuario.id,
        )
    assert erro.value.codigo == "ARQUIVO_NAO_E_PDF"


async def test_enviar_regra_recusa_pdf_grande_demais(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    usuario = await _arbitro(db_session, "coord-regra-5@tjr.app")

    with pytest.raises(AppError) as erro:
        await enviar_regra(
            db_session,
            modalidade.id,
            TipoRegra.MANUAL,
            nome_arquivo="manual.pdf",
            conteudo=PDF + b"0" * TAMANHO_MAXIMO_BYTES,
            usuario_id=usuario.id,
        )
    assert erro.value.codigo == "ARQUIVO_GRANDE_DEMAIS"


async def test_enviar_regra_para_modalidade_inexistente_retorna_404(db_session):
    usuario = await _arbitro(db_session, "coord-regra-6@tjr.app")

    with pytest.raises(AppError) as erro:
        await enviar_regra(
            db_session,
            uuid.uuid4(),
            TipoRegra.MANUAL,
            nome_arquivo="manual.pdf",
            conteudo=PDF,
            usuario_id=usuario.id,
        )
    assert erro.value.status_code == 404


async def test_remover_regra_apaga_so_aquele_pdf(db_session):
    evento = await _evento(db_session)
    modalidade = await _modalidade(db_session, evento)
    usuario = await _arbitro(db_session, "coord-regra-7@tjr.app")
    for tipo in TipoRegra:
        await enviar_regra(
            db_session,
            modalidade.id,
            tipo,
            nome_arquivo="x.pdf",
            conteudo=PDF,
            usuario_id=usuario.id,
        )

    await remover_regra(db_session, modalidade.id, TipoRegra.MANUAL)

    with pytest.raises(AppError):
        await obter_regra(db_session, modalidade.id, TipoRegra.MANUAL)
    assert (await obter_regra(db_session, modalidade.id, TipoRegra.CADERNO_ALUNO)).conteudo == PDF


async def test_listar_regras_do_evento_mostra_toda_modalidade_por_nome_com_os_pdfs_que_tem(
    db_session,
):
    evento = await _evento(db_session)
    sumo = await _modalidade(db_session, evento, nome="Sumô")
    await _modalidade(db_session, evento, nome="Dança")
    usuario = await _arbitro(db_session, "coord-regra-8@tjr.app")
    await enviar_regra(
        db_session,
        sumo.id,
        TipoRegra.CADERNO_ALUNO,
        nome_arquivo="caderno.pdf",
        conteudo=PDF,
        usuario_id=usuario.id,
    )

    lista = await listar_regras_do_evento(db_session, evento.id)

    assert [m.nome for m in lista] == ["Dança", "Sumô"]
    assert lista[0].regras == []
    assert [(r.tipo, r.nome_arquivo) for r in lista[1].regras] == [
        (TipoRegra.CADERNO_ALUNO, "caderno.pdf")
    ]
