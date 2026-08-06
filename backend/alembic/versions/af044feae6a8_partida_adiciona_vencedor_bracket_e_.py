"""partida adiciona vencedor bracket e equipe_b nullable

Revision ID: af044feae6a8
Revises: cc920ef35f85
Create Date: 2026-08-01 14:39:30.669246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'af044feae6a8'
down_revision: Union[str, None] = 'cc920ef35f85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('partida', 'equipe_b_id', nullable=True)

    partida_bracket_enum = postgresql.ENUM('SUPERIOR', 'INFERIOR', name='partida_bracket')
    partida_bracket_enum.create(op.get_bind())

    op.add_column(
        'partida',
        sa.Column('vencedor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipe.id'), nullable=True),
    )
    op.add_column('partida', sa.Column('bracket', partida_bracket_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('partida', 'bracket')
    op.drop_column('partida', 'vencedor_id')
    op.execute('DROP TYPE partida_bracket')
    op.alter_column('partida', 'equipe_b_id', nullable=False)
