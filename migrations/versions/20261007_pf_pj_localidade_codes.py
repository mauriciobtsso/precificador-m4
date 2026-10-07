"""Add person classification and TD locality code fields.

Revision ID: 20261007_pf_pj_localidade
Revises: 20261007_importacoes_tipo
Create Date: 2026-10-07

All columns are nullable and have no server default, so existing rows are not
rewritten or assigned guessed values by this schema migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261007_pf_pj_localidade"
down_revision = "20261007_importacoes_tipo"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clientes", sa.Column("tipo_pessoa", sa.String(length=20), nullable=True))
    op.add_column("clientes", sa.Column("codigo_uf_nascimento", sa.String(length=20), nullable=True))
    op.add_column("clientes", sa.Column("codigo_cidade_nascimento", sa.String(length=20), nullable=True))
    op.add_column("clientes", sa.Column("codigo_estado_civil", sa.String(length=20), nullable=True))
    op.add_column("clientes_enderecos", sa.Column("codigo_estado", sa.String(length=20), nullable=True))
    op.add_column("clientes_enderecos", sa.Column("codigo_cidade", sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column("clientes_enderecos", "codigo_cidade")
    op.drop_column("clientes_enderecos", "codigo_estado")
    op.drop_column("clientes", "codigo_estado_civil")
    op.drop_column("clientes", "codigo_cidade_nascimento")
    op.drop_column("clientes", "codigo_uf_nascimento")
    op.drop_column("clientes", "tipo_pessoa")
