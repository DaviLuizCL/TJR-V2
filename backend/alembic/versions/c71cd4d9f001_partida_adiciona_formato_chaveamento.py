"""partida adiciona formato_chaveamento

Revision ID: c71cd4d9f001
Revises: 353d40a6fcc5
Create Date: 2026-08-26 22:22:39.398908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c71cd4d9f001'
down_revision: Union[str, None] = '353d40a6fcc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    formato_chaveamento_enum = postgresql.ENUM(
        'MATA_MATA', 'TODOS_CONTRA_TODOS', name='formato_chaveamento', create_type=False
    )
    op.add_column(
        'partida',
        sa.Column('formato_chaveamento', formato_chaveamento_enum, nullable=True),
    )
    # Backfill com o formato que a modalidade tinha configurado quando a
    # partida foi criada (unico dado historico disponivel); linha sem
    # modalidade.formato_chaveamento definido (nao deveria existir em
    # partida ja criada, mas por seguranca) cai em MATA_MATA.
    op.execute(
        """
        UPDATE partida p
        SET formato_chaveamento = COALESCE(m.formato_chaveamento, 'MATA_MATA')
        FROM rodada r
        JOIN modalidade m ON m.id = r.modalidade_id
        WHERE p.rodada_id = r.id
        """
    )
    op.alter_column('partida', 'formato_chaveamento', nullable=False)


def downgrade() -> None:
    op.drop_column('partida', 'formato_chaveamento')
