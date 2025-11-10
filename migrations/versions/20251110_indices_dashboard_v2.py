"""Recriado índices de performance — Dashboard

Revision ID: 20251110_indices_dashboard_v2
Revises: 447f399d6bc1
Create Date: 2025-11-10 13:57:03.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251110_indices_dashboard_v2"
down_revision = "447f399d6bc1"
branch_labels = None
depends_on = None


def upgrade():
    # Índices de performance para o dashboard e consultas frequentes

    # Tabela produtos
    op.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos (nome);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_produtos_categoria_id ON produtos (categoria_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_produtos_atualizado_em ON produtos (atualizado_em);")

    # Tabela vendas
    op.execute("CREATE INDEX IF NOT EXISTS idx_vendas_data_abertura ON vendas (data_abertura);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_vendas_valor_total ON vendas (valor_total);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_vendas_cliente_id ON vendas (cliente_id);")

    # Tabela itens_venda
    op.execute("CREATE INDEX IF NOT EXISTS idx_itemvenda_venda_id ON itens_venda (venda_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_itemvenda_produto_nome ON itens_venda (produto_nome);")

    # Tabela clientes
    op.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes (nome);")

    # Tabela importacoes_log (para filtros recentes)
    op.execute("CREATE INDEX IF NOT EXISTS idx_importacoes_log_data_hora ON importacoes_log (data_hora DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_importacoes_log_tipo ON importacoes_log (tipo);")


def downgrade():
    # Remover índices criados
    op.execute("DROP INDEX IF EXISTS idx_produtos_nome;")
    op.execute("DROP INDEX IF EXISTS idx_produtos_categoria_id;")
    op.execute("DROP INDEX IF EXISTS idx_produtos_atualizado_em;")

    op.execute("DROP INDEX IF EXISTS idx_vendas_data_abertura;")
    op.execute("DROP INDEX IF EXISTS idx_vendas_valor_total;")
    op.execute("DROP INDEX IF EXISTS idx_vendas_cliente_id;")

    op.execute("DROP INDEX IF EXISTS idx_itemvenda_venda_id;")
    op.execute("DROP INDEX IF EXISTS idx_itemvenda_produto_nome;")

    op.execute("DROP INDEX IF EXISTS idx_clientes_nome;")

    op.execute("DROP INDEX IF EXISTS idx_importacoes_log_data_hora;")
    op.execute("DROP INDEX IF EXISTS idx_importacoes_log_tipo;")
