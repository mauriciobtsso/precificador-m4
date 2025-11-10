"""Merge heads após correção de índices

Revision ID: 569166e05111
Revises: c4f3b85a0f52, 20251110_indices_dashboard_v2
Create Date: 2025-11-10 14:02:02.303427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '569166e05111'
down_revision = ('c4f3b85a0f52', '20251110_indices_dashboard_v2')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
