"""Adiciona IDs externos de munição ao cadastro e ao inventário.

Revision ID: 20261117_id_municao_sisgcorp
Revises: 20261006_inventario_municoes
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_id_municao_sisgcorp"
down_revision = "20261006_inventario_municoes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("produtos", sa.Column("id_municao", sa.String(length=80), nullable=True))
    op.create_index("ix_produtos_id_municao", "produtos", ["id_municao"], unique=False)
    op.add_column(
        "estoque_conferencia_municao_itens",
        sa.Column("id_municao", sa.String(length=80), nullable=True),
    )


def downgrade():
    op.drop_column("estoque_conferencia_municao_itens", "id_municao")
    op.drop_index("ix_produtos_id_municao", table_name="produtos")
    op.drop_column("produtos", "id_municao")
