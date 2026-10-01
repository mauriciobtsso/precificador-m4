"""Adiciona vídeos à galeria pública dos produtos.

Revision ID: 20261001_produto_videos
Revises: 20260930_produto_fotos
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_produto_videos"
down_revision = "20260930_produto_fotos"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "produto_videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_produto_videos_produto_id", "produto_videos", ["produto_id"])
    op.create_index("idx_produto_video_produto_ordem", "produto_videos", ["produto_id", "ordem"])


def downgrade():
    op.drop_index("idx_produto_video_produto_ordem", table_name="produto_videos")
    op.drop_index("ix_produto_videos_produto_id", table_name="produto_videos")
    op.drop_table("produto_videos")
