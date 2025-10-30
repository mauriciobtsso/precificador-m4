"""merge heads

Revision ID: ec3f3f654bab
Revises: add_foto_url_produto_20251022, 20251028_01_add_compras_nf_itens
Create Date: 2025-10-28 11:13:57.367490

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ec3f3f654bab'
down_revision = ('add_foto_url_produto_20251022', '20251028_01_add_compras_nf_itens')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
