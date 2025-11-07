"""Criar tabela importacoes_log

Revision ID: 071120251741
Revises: ade965dc7e78
Create Date: 2025-11-07 17:41:36.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '071120251741'
down_revision = 'ade965dc7e78'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'importacoes_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('usuario', sa.String(length=100), nullable=True),
        sa.Column('data_hora', sa.DateTime(timezone=True), nullable=True),
        sa.Column('novos', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('atualizados', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('total', sa.Integer(), nullable=False, server_default="0")
    )


def downgrade():
    op.drop_table('importacoes_log')
