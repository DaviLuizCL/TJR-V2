import pytest

from app.core.deps import exigir_papel, obter_papel_atual
from app.core.errors import AppError
from app.core.security import criar_access_token, hash_senha
from app.models.usuario import Papel, Usuario


def _usuario(papel: Papel) -> Usuario:
    return Usuario(nome="Teste", email="teste@tjr.app", senha_hash="x", papel=papel)


async def test_exigir_papel_permite_papel_autorizado():
    checar = exigir_papel(Papel.COORDENADOR)
    usuario = _usuario(Papel.COORDENADOR)

    resultado = await checar(usuario=usuario)

    assert resultado is usuario


async def test_exigir_papel_permite_um_entre_varios_papeis():
    checar = exigir_papel(Papel.COORDENADOR, Papel.SECRETARIA)
    usuario = _usuario(Papel.SECRETARIA)

    resultado = await checar(usuario=usuario)

    assert resultado is usuario


async def test_exigir_papel_nega_papel_nao_autorizado():
    checar = exigir_papel(Papel.COORDENADOR)
    usuario = _usuario(Papel.ARBITRO)

    with pytest.raises(AppError) as exc_info:
        await checar(usuario=usuario)

    assert exc_info.value.status_code == 403
    assert exc_info.value.codigo == "PAPEL_NAO_AUTORIZADO"


async def test_obter_papel_atual_sem_token_retorna_publico(db_session):
    papel = await obter_papel_atual(token=None, db=db_session)

    assert papel == Papel.PUBLICO


async def test_obter_papel_atual_com_token_invalido_retorna_publico(db_session):
    papel = await obter_papel_atual(token="lixo-nao-e-jwt", db=db_session)

    assert papel == Papel.PUBLICO


async def test_obter_papel_atual_com_token_valido_retorna_papel_do_usuario(db_session):
    usuario = Usuario(
        nome="Coordenadora",
        email="coord-deps@tjr.app",
        senha_hash=hash_senha("senha-123"),
        papel=Papel.COORDENADOR,
    )
    db_session.add(usuario)
    await db_session.flush()
    token = criar_access_token(sub=str(usuario.id), papel=usuario.papel.value)

    papel = await obter_papel_atual(token=token, db=db_session)

    assert papel == Papel.COORDENADOR
