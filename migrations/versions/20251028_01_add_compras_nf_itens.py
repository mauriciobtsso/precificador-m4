"""add compras_nf e compras_item tables

Revision ID: 20251028_01_add_compras_nf_itens
Revises: 154741188876
Create Date: 2025-10-28 09:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# Revisões
revision = '20251028_01_add_compras_nf_itens'
down_revision = '154741188876'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'compra_nf',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('numero', sa.String(50), nullable=True),
        sa.Column('chave', sa.String(200), unique=True, nullable=True),
        sa.Column('fornecedor', sa.String(120), nullable=True),
        sa.Column('data_emissao', sa.DateTime, nullable=True),
        sa.Column('total', sa.Numeric(12, 2), nullable=True),
        sa.Column('criado_em', sa.DateTime, default=datetime.utcnow)
    )

    op.create_table(
        'compra_item',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('nf_id', sa.Integer, sa.ForeignKey('compra_nf.id', ondelete='CASCADE')),
        sa.Column('descricao', sa.String(250), nullable=True),
        sa.Column('marca', sa.String(100), nullable=True),
        sa.Column('modelo', sa.String(100), nullable=True),
        sa.Column('calibre', sa.String(50), nullable=True),
        sa.Column('lote', sa.String(100), nullable=True),
        sa.Column('quantidade', sa.Numeric(10, 2), nullable=True),
        sa.Column('valor_unitario', sa.Numeric(10, 2), nullable=True),
        sa.Column('valor_total', sa.Numeric(12, 2), nullable=True),
    )


def downgrade():
    op.drop_table('compra_item')
    op.drop_table('compra_nf')
