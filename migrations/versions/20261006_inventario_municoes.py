"""Criar conferência física de inventário de munições.

Revision ID: 20261006_inventario_municoes
Revises: 20261001_tour360_acessorios
"""
from alembic import op
import sqlalchemy as sa

revision = "20261006_inventario_municoes"
down_revision = "20261001_tour360_acessorios"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "estoque_conferencias_municao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_conferencia", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="aberta"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("loja_cnpj", sa.String(length=30), nullable=True),
        sa.Column("loja_nome", sa.String(length=180), nullable=True),
        sa.Column("loja_endereco", sa.Text(), nullable=True),
        sa.Column("loja_cr", sa.String(length=50), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("finalizado_em", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_estoque_conferencias_municao_data_conferencia", "estoque_conferencias_municao", ["data_conferencia"])
    op.create_index("ix_estoque_conferencias_municao_status", "estoque_conferencias_municao", ["status"])
    op.create_table(
        "estoque_conferencia_municao_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conferencia_id", sa.Integer(), sa.ForeignKey("estoque_conferencias_municao.id", ondelete="CASCADE"), nullable=False),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=True),
        sa.Column("codigo_municao", sa.String(length=50), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("calibre", sa.String(length=80), nullable=True),
        sa.Column("lote", sa.String(length=80), nullable=True),
        sa.Column("identificacao_embalagem", sa.String(length=120), nullable=False),
        sa.Column("quantidade_embalagem", sa.Integer(), nullable=False),
        sa.Column("quantidade_total", sa.Integer(), nullable=False),
        sa.Column("lido_em", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("conferencia_id", "identificacao_embalagem", name="uq_conferencia_embalagem"),
    )
    op.create_index("ix_estoque_conferencia_municao_itens_conferencia_id", "estoque_conferencia_municao_itens", ["conferencia_id"])
    op.create_index("ix_estoque_conferencia_municao_itens_produto_id", "estoque_conferencia_municao_itens", ["produto_id"])


def downgrade():
    op.drop_table("estoque_conferencia_municao_itens")
    op.drop_index("ix_estoque_conferencias_municao_status", table_name="estoque_conferencias_municao")
    op.drop_index("ix_estoque_conferencias_municao_data_conferencia", table_name="estoque_conferencias_municao")
    op.drop_table("estoque_conferencias_municao")
