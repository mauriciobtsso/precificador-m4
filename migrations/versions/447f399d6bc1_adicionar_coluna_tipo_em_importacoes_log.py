"""adicionar coluna tipo em importacoes_log

Revision ID: 447f399d6bc1
Revises: 071120251741
Create Date: 2025-11-08 11:27:29.805644
"""

from alembic import op
import sqlalchemy as sa

# Revisões
revision = '447f399d6bc1'
down_revision = '071120251741'
branch_labels = None
depends_on = None


def upgrade():
    # Índice para filtros por data (consultas mensais no dashboard)
    op.execute("CREATE INDEX IF NOT EXISTS idx_vendas_data_abertura ON vendas (data_abertura DESC);")

    # Índice para joins de performance (ItemVenda → Produto)
    op.execute("CREATE INDEX IF NOT EXISTS idx_itemvenda_produto_id ON itens_venda (produto_id);")

    # Opcional: índice composto para buscas de vendas recentes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_vendas_mes_ano
        ON vendas (
            EXTRACT(YEAR FROM data_abertura),
            EXTRACT(MONTH FROM data_abertura)
        );
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_vendas_mes_ano;")
    op.execute("DROP INDEX IF EXISTS idx_itemvenda_produto_id;")
    op.execute("DROP INDEX IF EXISTS idx_vendas_data_abertura;")
