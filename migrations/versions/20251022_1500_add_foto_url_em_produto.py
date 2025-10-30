"""add foto_url em produto

Revision ID: add_foto_url_produto_20251022
Revises: 154741188876
Create Date: 2025-10-22 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_foto_url_produto_20251022'
down_revision = '154741188876'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('foto_url', sa.String(length=512), nullable=True))


def downgrade():
    with op.batch_alter_table('produto', schema=None) as batch_op:
        batch_op.drop_column('foto_url')
