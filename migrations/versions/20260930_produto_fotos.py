"""Adiciona galeria de fotos aos produtos.

Revision ID: 20260930_produto_fotos
Revises: 20260929_pix_snapshot
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260930_produto_fotos"
down_revision = "20260929_pix_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "produto_fotos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("eh_principal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_produto_fotos_produto_id", "produto_fotos", ["produto_id"])
    op.create_index("ix_produto_fotos_eh_principal", "produto_fotos", ["eh_principal"])
    op.create_index("idx_produto_foto_produto_ordem", "produto_fotos", ["produto_id", "ordem"])
    # Migra a foto antiga para a nova galeria sem alterar a URL pública.
    op.execute(sa.text("""
        INSERT INTO produto_fotos (produto_id, url, eh_principal, ordem, criado_em)
        SELECT id, foto_url, TRUE, 0, CURRENT_TIMESTAMP
          FROM produtos
         WHERE foto_url IS NOT NULL AND btrim(foto_url) <> ''
    """))


def downgrade():
    op.drop_index("idx_produto_foto_produto_ordem", table_name="produto_fotos")
    op.drop_index("ix_produto_fotos_eh_principal", table_name="produto_fotos")
    op.drop_index("ix_produto_fotos_produto_id", table_name="produto_fotos")
    op.drop_table("produto_fotos")
