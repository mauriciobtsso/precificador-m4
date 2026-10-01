"""Adiciona tour 360 e acessórios relacionados aos produtos.

Revision ID: 20261001_tour360_acessorios
Revises: 20261001_produto_videos
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_tour360_acessorios"
down_revision = "20261001_produto_videos"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "produto_tours_360",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=True),
        sa.Column("frames", sa.JSON(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("produto_id"),
    )
    op.create_index("ix_produto_tours_360_produto_id", "produto_tours_360", ["produto_id"])
    op.create_index("ix_produto_tours_360_ativo", "produto_tours_360", ["ativo"])

    op.create_table(
        "produto_acessorios",
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("acessorio_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acessorio_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("produto_id", "acessorio_id"),
    )
    op.create_index("idx_produto_acessorios_produto_ordem", "produto_acessorios", ["produto_id", "ordem"])


def downgrade():
    op.drop_index("idx_produto_acessorios_produto_ordem", table_name="produto_acessorios")
    op.drop_table("produto_acessorios")
    op.drop_index("ix_produto_tours_360_ativo", table_name="produto_tours_360")
    op.drop_index("ix_produto_tours_360_produto_id", table_name="produto_tours_360")
    op.drop_table("produto_tours_360")
