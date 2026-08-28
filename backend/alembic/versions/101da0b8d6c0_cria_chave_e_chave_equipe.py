"""cria chave e chave_equipe

Revision ID: 101da0b8d6c0
Revises: 610eb85a013e
Create Date: 2026-08-28 19:14:40.823147

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '101da0b8d6c0'
down_revision: Union[str, None] = '610eb85a013e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chave",
        sa.Column("modalidade_id", sa.UUID(), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["modalidade_id"], ["modalidade.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chave_modalidade_id"), "chave", ["modalidade_id"], unique=False)

    op.create_table(
        "chave_equipe",
        sa.Column("chave_id", sa.UUID(), nullable=False),
        sa.Column("equipe_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chave_id"], ["chave.id"]),
        sa.ForeignKeyConstraint(["equipe_id"], ["equipe.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_id", "equipe_id", name="uq_chave_equipe_chave_equipe"),
    )
    op.create_index(op.f("ix_chave_equipe_chave_id"), "chave_equipe", ["chave_id"], unique=False)
    op.create_index(op.f("ix_chave_equipe_equipe_id"), "chave_equipe", ["equipe_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chave_equipe_equipe_id"), table_name="chave_equipe")
    op.drop_index(op.f("ix_chave_equipe_chave_id"), table_name="chave_equipe")
    op.drop_table("chave_equipe")
    op.drop_index(op.f("ix_chave_modalidade_id"), table_name="chave")
    op.drop_table("chave")
