"""consolidacao adiciona ignora_menor_nota

Revision ID: a1c9f2e6b4d7
Revises: 945b3f35bf48
Create Date: 2026-08-04 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1c9f2e6b4d7'
down_revision: Union[str, None] = '945b3f35bf48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE consolidacao ADD VALUE 'IGNORA_MENOR_NOTA'")


def downgrade() -> None:
    op.execute('ALTER TYPE consolidacao RENAME TO consolidacao_antigo')
    consolidacao_enum = postgresql.ENUM(
        'SOMA_RODADAS', 'MELHOR_RODADA', 'MELHOR_N_RODADAS', name='consolidacao'
    )
    consolidacao_enum.create(op.get_bind())
    op.execute(
        'ALTER TABLE modalidade ALTER COLUMN consolidacao TYPE consolidacao '
        'USING consolidacao::text::consolidacao'
    )
    op.execute('DROP TYPE consolidacao_antigo')
