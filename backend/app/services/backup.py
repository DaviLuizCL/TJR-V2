"""Backup completo do banco, baixado pelo painel de Administracao.

Roda `pg_dump` em formato custom (o mesmo que o DEPLOY.md usa pra restaurar com
`pg_restore`). Precisa do pacote `postgresql-client` na imagem da api, com
versao >= a do servidor (imagem Debian 13 traz o client 17, servidor e 16).
"""

import asyncio
import os

from sqlalchemy.engine import make_url

from app.core.errors import AppError


async def gerar_backup(database_url: str) -> bytes:
    url = make_url(database_url)
    argumentos = [
        "pg_dump",
        "--format=custom",
        "-h",
        url.host or "localhost",
        "-p",
        str(url.port or 5432),
        "-U",
        url.username or "postgres",
        "-d",
        url.database or "",
    ]
    # Senha so pela variavel de ambiente: argumento de processo aparece em `ps`.
    ambiente = {**os.environ, "PGPASSWORD": url.password or ""}

    try:
        processo = await asyncio.create_subprocess_exec(
            *argumentos,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=ambiente,
        )
    except FileNotFoundError as erro:
        raise AppError(
            codigo="BACKUP_INDISPONIVEL",
            mensagem="O programa de backup (pg_dump) nao esta instalado no servidor.",
            status_code=500,
        ) from erro

    saida, _ = await processo.communicate()
    if processo.returncode != 0:
        raise AppError(
            codigo="BACKUP_FALHOU",
            mensagem="Nao foi possivel gerar o backup agora. Tente de novo em instantes.",
            status_code=500,
        )
    return saida
