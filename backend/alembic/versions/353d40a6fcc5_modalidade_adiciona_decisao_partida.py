"""modalidade adiciona decisao_partida

Revision ID: 353d40a6fcc5
Revises: 1f47e59541db
Create Date: 2026-08-21 21:12:21.458325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '353d40a6fcc5'
down_revision: Union[str, None] = '1f47e59541db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    decisao_partida_enum = postgresql.ENUM(
        'COMBATES_VENCIDOS', 'SOMA_PONTOS', name='decisao_partida'
    )
    decisao_partida_enum.create(op.get_bind())
    op.add_column(
        'modalidade',
        sa.Column(
            'decisao_partida',
            decisao_partida_enum,
            nullable=False,
            server_default='COMBATES_VENCIDOS',
        ),
    )


def downgrade() -> None:
    op.drop_column('modalidade', 'decisao_partida')
    op.execute('DROP TYPE decisao_partida')
