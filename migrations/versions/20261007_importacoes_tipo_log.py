"""Add missing type column to import log.

Revision ID: 20261007_importacoes_tipo
Revises: 20261006_inventario_municoes
Create Date: 2026-10-07

The historical migration labelled as adding this column did not actually add it.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261007_importacoes_tipo"
down_revision = "20261006_inventario_municoes"
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows (if any) receive the legacy/default category safely.
    op.add_column(
        "importacoes_log",
        sa.Column(
            "tipo",
            sa.String(length=50),
            nullable=False,
            server_default="produtos",
        ),
    )


def downgrade():
    op.drop_column("importacoes_log", "tipo")
