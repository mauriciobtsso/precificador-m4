"""Adiciona snapshots da cobrança e dados PIX aos pedidos da loja.

Revision ID: 20260929_pix_snapshot
Revises: 20260929_taxas_link
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_pix_snapshot"
down_revision = "20260929_taxas_link"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pedidos", sa.Column("total_cobrado", sa.Numeric(12, 2), nullable=True))
    op.add_column("pedidos", sa.Column("taxa_aplicada", sa.Numeric(8, 4), nullable=True))
    op.add_column("pedidos", sa.Column("desconto_aplicado", sa.Numeric(12, 2), nullable=True))
    op.add_column("pedidos", sa.Column("valor_parcela", sa.Numeric(12, 2), nullable=True))
    op.add_column("pedidos", sa.Column("checkout_key", sa.String(length=36), nullable=True))
    op.add_column("pedidos", sa.Column("pagarme_pix_qr_code", sa.Text(), nullable=True))
    op.add_column("pedidos", sa.Column("pagarme_pix_qr_code_url", sa.String(length=1024), nullable=True))
    op.add_column("pedidos", sa.Column("pagarme_pix_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_pedidos_checkout_key", "pedidos", ["checkout_key"], unique=True)


def downgrade():
    op.drop_index("ix_pedidos_checkout_key", table_name="pedidos")
    op.drop_column("pedidos", "pagarme_pix_expires_at")
    op.drop_column("pedidos", "pagarme_pix_qr_code_url")
    op.drop_column("pedidos", "pagarme_pix_qr_code")
    op.drop_column("pedidos", "checkout_key")
    op.drop_column("pedidos", "valor_parcela")
    op.drop_column("pedidos", "desconto_aplicado")
    op.drop_column("pedidos", "taxa_aplicada")
    op.drop_column("pedidos", "total_cobrado")
