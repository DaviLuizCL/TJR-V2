import pytest

from app.core.errors import AppError
from app.services import backup


class _ProcessoFalso:
    def __init__(self, returncode, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _substituir_subprocess(monkeypatch, processo, chamadas):
    async def _falso(*args, **kwargs):
        chamadas.append((args, kwargs))
        return processo

    monkeypatch.setattr(backup.asyncio, "create_subprocess_exec", _falso)


async def test_gerar_backup_roda_pg_dump_em_formato_custom_e_devolve_o_conteudo(monkeypatch):
    chamadas = []
    _substituir_subprocess(monkeypatch, _ProcessoFalso(0, stdout=b"PGDMP..."), chamadas)

    conteudo = await backup.gerar_backup("postgresql+asyncpg://tjr:segredo@db:5432/tjr")

    assert conteudo == b"PGDMP..."
    args, kwargs = chamadas[0]
    assert args[0] == "pg_dump"
    assert "--format=custom" in args
    assert ["-h", "db"] == list(args[args.index("-h") : args.index("-h") + 2])
    assert ["-d", "tjr"] == list(args[args.index("-d") : args.index("-d") + 2])
    assert ["-U", "tjr"] == list(args[args.index("-U") : args.index("-U") + 2])


async def test_gerar_backup_passa_a_senha_por_variavel_de_ambiente_nunca_por_argumento(
    monkeypatch,
):
    chamadas = []
    _substituir_subprocess(monkeypatch, _ProcessoFalso(0, stdout=b"x"), chamadas)

    await backup.gerar_backup("postgresql+asyncpg://tjr:segredo@db:5432/tjr")

    args, kwargs = chamadas[0]
    assert "segredo" not in " ".join(args)
    assert kwargs["env"]["PGPASSWORD"] == "segredo"


async def test_gerar_backup_falha_vira_erro_padronizado(monkeypatch):
    _substituir_subprocess(monkeypatch, _ProcessoFalso(1, stderr=b"connection refused"), [])

    with pytest.raises(AppError) as erro:
        await backup.gerar_backup("postgresql+asyncpg://tjr:segredo@db:5432/tjr")

    assert erro.value.codigo == "BACKUP_FALHOU"
    assert "segredo" not in erro.value.mensagem


async def test_gerar_backup_sem_pg_dump_instalado_vira_erro_padronizado(monkeypatch):
    async def _sem_programa(*args, **kwargs):
        raise FileNotFoundError("pg_dump")

    monkeypatch.setattr(backup.asyncio, "create_subprocess_exec", _sem_programa)

    with pytest.raises(AppError) as erro:
        await backup.gerar_backup("postgresql+asyncpg://tjr:segredo@db:5432/tjr")

    assert erro.value.codigo == "BACKUP_INDISPONIVEL"
