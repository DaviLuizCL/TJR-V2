"""modalidade adiciona ranking liberado

Revision ID: cc920ef35f85
Revises: cb5fac7a7b31
Create Date: 2026-08-01 13:01:50.301764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc920ef35f85'
down_revision: Union[str, None] = 'cb5fac7a7b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'modalidade',
        sa.Column('ranking_liberado', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('modalidade', 'ranking_liberado')
