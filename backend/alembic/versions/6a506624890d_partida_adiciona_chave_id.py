"""partida adiciona chave_id

Revision ID: 6a506624890d
Revises: 101da0b8d6c0
Create Date: 2026-08-28 19:14:42.990328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a506624890d'
down_revision: Union[str, None] = '101da0b8d6c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("partida", sa.Column("chave_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_partida_chave_id_chave", "partida", "chave", ["chave_id"], ["id"]
    )
    op.create_index(op.f("ix_partida_chave_id"), "partida", ["chave_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_partida_chave_id"), table_name="partida")
    op.drop_constraint("fk_partida_chave_id_chave", "partida", type_="foreignkey")
    op.drop_column("partida", "chave_id")
