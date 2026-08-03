"""fix: resolve divergencia de multiplos heads

Revision ID: eb1852596428
Revises: 20260802_fuzzy_search_trgm, 6f927cdcc5e2
Create Date: 2026-08-03 09:24:54.773031

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb1852596428'
down_revision = ('20260802_fuzzy_search_trgm', '6f927cdcc5e2')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
