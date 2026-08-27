"""lancamento adiciona tempo_gasto_seg

Revision ID: 610eb85a013e
Revises: c71cd4d9f001
Create Date: 2026-08-26 23:36:16.428684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '610eb85a013e'
down_revision: Union[str, None] = 'c71cd4d9f001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lancamento', sa.Column('tempo_gasto_seg', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('lancamento', 'tempo_gasto_seg')
