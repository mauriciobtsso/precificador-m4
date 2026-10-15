"""Expand certidao types for assisted portal filling.

Revision ID: 20261015_expand_certidoes
Revises: 20261014_editable_faq
"""
from alembic import op

revision = "20261015_expand_certidoes"
down_revision = "20261014_editable_faq"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL enum values are additive and safe to deploy before application code.
    for value in ("estadual_mppi", "federal_mpf", "federal_cjf", "policial_pi"):
        op.execute(f"ALTER TYPE certidao_tipo_enum ADD VALUE IF NOT EXISTS '{value}'")


def downgrade():
    # PostgreSQL does not support removing enum labels safely; leave labels in place.
    pass
