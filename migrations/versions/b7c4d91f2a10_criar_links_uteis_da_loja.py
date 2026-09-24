"""Criar links úteis da loja.

Revision ID: b7c4d91f2a10
Revises: aefc868
"""
from alembic import op
import sqlalchemy as sa


revision = "b7c4d91f2a10"
down_revision = "aefc868"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loja_links_uteis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("resumo", sa.String(length=500), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loja_links_uteis_ativo", "loja_links_uteis", ["ativo"], unique=False)
    op.create_index("ix_loja_links_uteis_ordem", "loja_links_uteis", ["ordem"], unique=False)


def downgrade():
    op.drop_index("ix_loja_links_uteis_ordem", table_name="loja_links_uteis")
    op.drop_index("ix_loja_links_uteis_ativo", table_name="loja_links_uteis")
    op.drop_table("loja_links_uteis")
