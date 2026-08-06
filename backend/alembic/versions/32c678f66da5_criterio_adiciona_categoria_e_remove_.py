"""criterio: adiciona categoria e remove PENALIDADE de tipo

Revision ID: 32c678f66da5
Revises: de2bcad3385f
Create Date: 2026-07-28 18:43:31.121946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '32c678f66da5'
down_revision: Union[str, None] = 'de2bcad3385f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    categoria_enum = postgresql.ENUM('PONTUACAO', 'PENALIDADE', name='criterio_categoria')
    categoria_enum.create(op.get_bind())

    op.add_column('criterio', sa.Column('categoria', categoria_enum, nullable=True))

    # Dado existente: PENALIDADE (tipo) vira categoria=PENALIDADE + tipo=CONTADOR
    # (o comportamento antigo de PENALIDADE era identico ao CONTADOR, so que
    # subtraindo). Qualquer outro tipo existente vira categoria=PONTUACAO.
    op.execute(
        "UPDATE criterio SET categoria = CASE WHEN tipo = 'PENALIDADE' "
        "THEN 'PENALIDADE' ELSE 'PONTUACAO' END::criterio_categoria"
    )
    op.execute("UPDATE criterio SET tipo = 'CONTADOR' WHERE tipo = 'PENALIDADE'")

    op.alter_column('criterio', 'categoria', nullable=False)

    # Encolhe o enum criterio_tipo removendo PENALIDADE (Postgres nao suporta
    # DROP VALUE em enum; e preciso recriar o tipo).
    op.execute('ALTER TYPE criterio_tipo RENAME TO criterio_tipo_antigo')
    novo_tipo_enum = postgresql.ENUM(
        'CONTADOR', 'BOOLEANO', 'ESCALA', 'MODIFICADOR', name='criterio_tipo'
    )
    novo_tipo_enum.create(op.get_bind())
    op.execute(
        'ALTER TABLE criterio ALTER COLUMN tipo TYPE criterio_tipo '
        'USING tipo::text::criterio_tipo'
    )
    op.execute('DROP TYPE criterio_tipo_antigo')


def downgrade() -> None:
    op.execute('ALTER TYPE criterio_tipo RENAME TO criterio_tipo_novo')
    tipo_antigo_enum = postgresql.ENUM(
        'CONTADOR', 'BOOLEANO', 'ESCALA', 'PENALIDADE', 'MODIFICADOR', name='criterio_tipo'
    )
    tipo_antigo_enum.create(op.get_bind())
    op.execute(
        'ALTER TABLE criterio ALTER COLUMN tipo TYPE criterio_tipo '
        'USING tipo::text::criterio_tipo'
    )
    op.execute(
        "UPDATE criterio SET tipo = 'PENALIDADE' WHERE categoria = 'PENALIDADE' "
        "AND tipo = 'CONTADOR'"
    )
    op.execute('DROP TYPE criterio_tipo_novo')

    op.drop_column('criterio', 'categoria')
    op.execute('DROP TYPE criterio_categoria')
