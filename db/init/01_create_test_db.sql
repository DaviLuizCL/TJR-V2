-- Banco separado para a suite de testes (pytest cria/derruba tabelas aqui,
-- nunca no banco de desenvolvimento migrado via Alembic).
SELECT 'CREATE DATABASE tjr_test OWNER tjr'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'tjr_test')\gexec
