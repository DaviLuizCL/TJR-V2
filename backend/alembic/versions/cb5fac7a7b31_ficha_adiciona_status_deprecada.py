"""ficha adiciona status deprecada

Revision ID: cb5fac7a7b31
Revises: 0b627cd33b88
Create Date: 2026-08-01 12:47:01.247347

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cb5fac7a7b31'
down_revision: Union[str, None] = '0b627cd33b88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ficha_status ADD VALUE 'DEPRECADA'")


def downgrade() -> None:
    op.execute('ALTER TYPE ficha_status RENAME TO ficha_status_antigo')
    ficha_status_enum = postgresql.ENUM(
        'RASCUNHO', 'PUBLICADA', 'SUBSTITUIDA', name='ficha_status'
    )
    ficha_status_enum.create(op.get_bind())
    op.execute(
        'ALTER TABLE ficha ALTER COLUMN status TYPE ficha_status '
        'USING status::text::ficha_status'
    )
    op.execute('DROP TYPE ficha_status_antigo')
