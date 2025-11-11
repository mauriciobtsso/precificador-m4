"""add indexes produtos performance

Revision ID: 318aba777f81
Revises: ec3eef5b0192
Create Date: 2025-11-11 15:30:23.043750

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '318aba777f81'
down_revision = 'ec3eef5b0192'
branch_labels = None
depends_on = None


def upgrade():
    # Índices individuais
    op.create_index("idx_produto_nome", "produtos", ["nome"])
    op.create_index("idx_produto_codigo", "produtos", ["codigo"])
    op.create_index("idx_produto_categoria", "produtos", ["categoria_id"])
    op.create_index("idx_produto_marca", "produtos", ["marca_id"])
    op.create_index("idx_produto_calibre", "produtos", ["calibre_id"])
    op.create_index("idx_produto_tipo", "produtos", ["tipo_id"])
    op.create_index("idx_produto_criado_em", "produtos", ["criado_em"])
    op.create_index("idx_produto_atualizado_em", "produtos", ["atualizado_em"])

    # Índices adicionais para histórico
    op.create_index("idx_historico_produto_id", "produto_historico", ["produto_id"])
    op.create_index("idx_historico_usuario_id", "produto_historico", ["usuario_id"])
    op.create_index("idx_historico_data_modificacao", "produto_historico", ["data_modificacao"])
    op.create_index("idx_historico_origem", "produto_historico", ["origem"])


def downgrade():
    # Remoção dos índices (rollback)
    op.drop_index("idx_produto_nome", table_name="produtos")
    op.drop_index("idx_produto_codigo", table_name="produtos")
    op.drop_index("idx_produto_categoria", table_name="produtos")
    op.drop_index("idx_produto_marca", table_name="produtos")
    op.drop_index("idx_produto_calibre", table_name="produtos")
    op.drop_index("idx_produto_tipo", table_name="produtos")
    op.drop_index("idx_produto_criado_em", table_name="produtos")
    op.drop_index("idx_produto_atualizado_em", table_name="produtos")

    op.drop_index("idx_historico_produto_id", table_name="produto_historico")
    op.drop_index("idx_historico_usuario_id", table_name="produto_historico")
    op.drop_index("idx_historico_data_modificacao", table_name="produto_historico")
    op.drop_index("idx_historico_origem", table_name="produto_historico")