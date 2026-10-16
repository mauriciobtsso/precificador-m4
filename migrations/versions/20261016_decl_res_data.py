"""Persist the latest residence declaration details per client.

Revision ID: 20261016_decl_res_data
Revises: 20261016_sep_end_res
"""
from alembic import op
import sqlalchemy as sa

revision = "20261016_decl_res_data"
down_revision = "20261016_sep_end_res"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clientes_declaracoes_residencia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("clientes.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("proprietario_nome", sa.String(length=180), nullable=False),
        sa.Column("proprietario_documento", sa.String(length=30), nullable=False),
        sa.Column("proprietario_rg", sa.String(length=50), nullable=False),
        sa.Column("proprietario_rg_emissor", sa.String(length=50), nullable=False),
        sa.Column("proprietario_endereco", sa.String(length=400), nullable=False),
        sa.Column("cliente_endereco", sa.String(length=400), nullable=False),
        sa.Column("vinculo", sa.String(length=100), nullable=False),
        sa.Column("local", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("clientes_declaracoes_residencia")
