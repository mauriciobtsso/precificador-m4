"""criar tabela estoque_itens (vinculo com produtos e fornecedores)

Revision ID: ec83b3f1622f
Revises: b671cf012a12
Create Date: 2025-10-30 18:29:19.005619
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ec83b3f1622f'
down_revision = 'b671cf012a12'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'estoque_itens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('produto_id', sa.Integer(), sa.ForeignKey('produtos.id'), nullable=False),
        sa.Column('fornecedor_id', sa.Integer(), sa.ForeignKey('clientes.id'), nullable=True),
        sa.Column('tipo_item', sa.String(50), nullable=True),
        sa.Column('numero_serie', sa.String(100), nullable=True, unique=True),
        sa.Column('lote', sa.String(100), nullable=True),
        sa.Column('numero_embalagem', sa.String(100), nullable=True),
        sa.Column('quantidade', sa.Integer(), nullable=False, default=1),
        sa.Column('status', sa.String(50), nullable=True, default='disponivel'),
        sa.Column('data_entrada', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('estoque_itens')
