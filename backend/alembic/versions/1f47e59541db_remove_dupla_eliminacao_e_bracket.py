"""remove dupla eliminacao e bracket

Revision ID: 1f47e59541db
Revises: 2e803240e889
Create Date: 2026-08-06 22:51:14.380294

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1f47e59541db'
down_revision: Union[str, None] = '2e803240e889'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Modalidade que ainda estiver com DUPLA_ELIMINACAO vira MATA_MATA antes
    # de estreitar o enum (senao a conversao de tipo abaixo falha).
    op.execute("UPDATE modalidade SET formato_chaveamento = 'MATA_MATA' WHERE formato_chaveamento = 'DUPLA_ELIMINACAO'")

    op.execute('ALTER TYPE formato_chaveamento RENAME TO formato_chaveamento_old')
    novo_enum = postgresql.ENUM('MATA_MATA', 'TODOS_CONTRA_TODOS', name='formato_chaveamento')
    novo_enum.create(op.get_bind())
    op.execute(
        'ALTER TABLE modalidade '
        'ALTER COLUMN formato_chaveamento TYPE formato_chaveamento '
        'USING formato_chaveamento::text::formato_chaveamento'
    )
    op.execute('DROP TYPE formato_chaveamento_old')

    op.drop_column('partida', 'bracket')
    op.execute('DROP TYPE partida_bracket')


def downgrade() -> None:
    partida_bracket_enum = postgresql.ENUM('SUPERIOR', 'INFERIOR', name='partida_bracket')
    partida_bracket_enum.create(op.get_bind())
    op.add_column('partida', sa.Column('bracket', partida_bracket_enum, nullable=True))

    op.execute('ALTER TYPE formato_chaveamento RENAME TO formato_chaveamento_new')
    antigo_enum = postgresql.ENUM(
        'MATA_MATA', 'TODOS_CONTRA_TODOS', 'DUPLA_ELIMINACAO', name='formato_chaveamento'
    )
    antigo_enum.create(op.get_bind())
    op.execute(
        'ALTER TABLE modalidade '
        'ALTER COLUMN formato_chaveamento TYPE formato_chaveamento '
        'USING formato_chaveamento::text::formato_chaveamento'
    )
    op.execute('DROP TYPE formato_chaveamento_new')
