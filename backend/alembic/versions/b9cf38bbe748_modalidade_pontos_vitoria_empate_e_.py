"""modalidade pontos vitoria empate e partida status empatada

Revision ID: b9cf38bbe748
Revises: af044feae6a8
Create Date: 2026-08-01 16:01:13.185139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9cf38bbe748'
down_revision: Union[str, None] = 'af044feae6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'modalidade',
        sa.Column('pontos_vitoria', sa.Numeric(), nullable=False, server_default='3'),
    )
    op.add_column(
        'modalidade',
        sa.Column('pontos_empate', sa.Numeric(), nullable=False, server_default='1'),
    )
    op.execute("ALTER TYPE partida_status ADD VALUE 'EMPATADA'")


def downgrade() -> None:
    op.drop_column('modalidade', 'pontos_empate')
    op.drop_column('modalidade', 'pontos_vitoria')
    # Postgres nao suporta DROP VALUE em enum; reverter o partida_status
    # exigiria recriar o tipo. Como nenhum dado deveria estar em EMPATADA
    # antes desta migration, deixamos o valor extra no enum (no-op seguro).
