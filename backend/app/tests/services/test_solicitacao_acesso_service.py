import uuid

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import hash_senha, verificar_senha
from app.models.audit_log import AuditLog
from app.models.solicitacao_acesso import SolicitacaoStatus
from app.models.usuario import Papel, Usuario
from app.schemas.solicitacao_acesso import SolicitacaoAcessoCreate
from app.services.solicitacao_acesso import (
    aprovar_solicitacao,
    listar_solicitacoes,
    recusar_solicitacao,
    solicitar_acesso,
    tem_solicitacao_pendente,
)


async def _coordenador(db) -> Usuario:
    usuario = Usuario(
        nome="Coord",
        email="coord-solic@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db.add(usuario)
    await db.flush()
    return usuario


def _pedido(email="juiz.novo@tjr.app", nome="Juiz Novo", senha="segredo1"):
    return SolicitacaoAcessoCreate(nome=nome, email=email, senha=senha)


async def test_solicitar_acesso_guarda_pedido_pendente_sem_criar_usuario(db_session):
    solicitacao = await solicitar_acesso(db_session, _pedido())

    assert solicitacao.status == SolicitacaoStatus.PENDENTE
    assert (
        await db_session.scalar(select(Usuario).where(Usuario.email == "juiz.novo@tjr.app")) is None
    )


async def test_solicitar_acesso_nao_guarda_a_senha_em_texto(db_session):
    solicitacao = await solicitar_acesso(db_session, _pedido(senha="segredo1"))

    assert solicitacao.senha_hash != "segredo1"
    assert verificar_senha("segredo1", solicitacao.senha_hash)


async def test_solicitar_acesso_recusa_email_que_ja_tem_conta(db_session):
    await _coordenador(db_session)

    with pytest.raises(AppError) as erro:
        await solicitar_acesso(db_session, _pedido(email="coord-solic@tjr.app"))
    assert erro.value.codigo == "EMAIL_JA_CADASTRADO"


async def test_solicitar_acesso_recusa_segundo_pedido_pendente_do_mesmo_email(db_session):
    await solicitar_acesso(db_session, _pedido())

    with pytest.raises(AppError) as erro:
        await solicitar_acesso(db_session, _pedido())
    assert erro.value.codigo == "SOLICITACAO_JA_PENDENTE"


async def test_quem_foi_recusado_pode_pedir_de_novo(db_session):
    coordenador = await _coordenador(db_session)
    primeira = await solicitar_acesso(db_session, _pedido())
    await recusar_solicitacao(db_session, primeira.id, usuario_id=coordenador.id)

    segunda = await solicitar_acesso(db_session, _pedido())

    assert segunda.status == SolicitacaoStatus.PENDENTE


async def test_listar_solicitacoes_traz_so_as_pendentes_mais_antigas_primeiro(db_session):
    coordenador = await _coordenador(db_session)
    primeira = await solicitar_acesso(db_session, _pedido(email="a@tjr.app"))
    recusada = await solicitar_acesso(db_session, _pedido(email="b@tjr.app"))
    terceira = await solicitar_acesso(db_session, _pedido(email="c@tjr.app"))
    await recusar_solicitacao(db_session, recusada.id, usuario_id=coordenador.id)

    pendentes = await listar_solicitacoes(db_session)

    assert [s.id for s in pendentes] == [primeira.id, terceira.id]


async def test_aprovar_cria_conta_de_juiz_com_a_senha_que_ele_escolheu(db_session):
    coordenador = await _coordenador(db_session)
    solicitacao = await solicitar_acesso(db_session, _pedido(senha="segredo1"))

    usuario = await aprovar_solicitacao(db_session, solicitacao.id, usuario_id=coordenador.id)

    assert usuario.papel == Papel.ARBITRO
    assert usuario.nome == "Juiz Novo"
    assert usuario.email == "juiz.novo@tjr.app"
    assert usuario.ativo is True
    assert verificar_senha("segredo1", usuario.senha_hash)
    assert solicitacao.status == SolicitacaoStatus.APROVADA
    assert solicitacao.decidido_por_id == coordenador.id
    assert solicitacao.decidido_em is not None
    assert solicitacao.usuario_criado_id == usuario.id


async def test_aprovar_grava_audit_log(db_session):
    coordenador = await _coordenador(db_session)
    solicitacao = await solicitar_acesso(db_session, _pedido())

    await aprovar_solicitacao(db_session, solicitacao.id, usuario_id=coordenador.id)

    log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entidade_id == solicitacao.id, AuditLog.acao == "APROVAR_ACESSO"
        )
    )
    assert log is not None
    assert log.usuario_id == coordenador.id
    assert "senha" not in str(log.depois)


async def test_recusar_nao_cria_conta_e_grava_audit_log(db_session):
    coordenador = await _coordenador(db_session)
    solicitacao = await solicitar_acesso(db_session, _pedido())

    await recusar_solicitacao(db_session, solicitacao.id, usuario_id=coordenador.id)

    assert solicitacao.status == SolicitacaoStatus.RECUSADA
    assert (
        await db_session.scalar(select(Usuario).where(Usuario.email == "juiz.novo@tjr.app")) is None
    )
    log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entidade_id == solicitacao.id, AuditLog.acao == "RECUSAR_ACESSO"
        )
    )
    assert log is not None


async def test_nao_da_pra_decidir_duas_vezes_o_mesmo_pedido(db_session):
    coordenador = await _coordenador(db_session)
    solicitacao = await solicitar_acesso(db_session, _pedido())
    await recusar_solicitacao(db_session, solicitacao.id, usuario_id=coordenador.id)

    with pytest.raises(AppError) as erro:
        await aprovar_solicitacao(db_session, solicitacao.id, usuario_id=coordenador.id)
    assert erro.value.codigo == "SOLICITACAO_JA_DECIDIDA"


async def test_aprovar_recusa_se_o_email_ganhou_conta_depois_do_pedido(db_session):
    coordenador = await _coordenador(db_session)
    solicitacao = await solicitar_acesso(db_session, _pedido())
    db_session.add(
        Usuario(
            nome="Criado na mao",
            email="juiz.novo@tjr.app",
            senha_hash=hash_senha("outra-senha"),
            papel=Papel.ARBITRO,
        )
    )
    await db_session.flush()

    with pytest.raises(AppError) as erro:
        await aprovar_solicitacao(db_session, solicitacao.id, usuario_id=coordenador.id)
    assert erro.value.codigo == "EMAIL_JA_CADASTRADO"


async def test_decidir_pedido_inexistente_retorna_404(db_session):
    coordenador = await _coordenador(db_session)

    with pytest.raises(AppError) as erro:
        await aprovar_solicitacao(db_session, uuid.uuid4(), usuario_id=coordenador.id)
    assert erro.value.codigo == "SOLICITACAO_NAO_ENCONTRADA"
    assert erro.value.status_code == 404


async def test_tem_solicitacao_pendente_so_com_a_senha_certa(db_session):
    await solicitar_acesso(db_session, _pedido(senha="segredo1"))

    assert await tem_solicitacao_pendente(db_session, "juiz.novo@tjr.app", "segredo1") is True
    assert await tem_solicitacao_pendente(db_session, "juiz.novo@tjr.app", "errada") is False
    assert await tem_solicitacao_pendente(db_session, "outro@tjr.app", "segredo1") is False


async def test_aprovar_pode_criar_conta_de_coordenador(db_session):
    coordenador = await _coordenador(db_session)
    solicitacao = await solicitar_acesso(db_session, _pedido())

    usuario = await aprovar_solicitacao(
        db_session, solicitacao.id, usuario_id=coordenador.id, papel=Papel.COORDENADOR
    )

    assert usuario.papel == Papel.COORDENADOR
    log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entidade_id == solicitacao.id, AuditLog.acao == "APROVAR_ACESSO"
        )
    )
    assert log.depois["papel"] == "COORDENADOR"
