"""Unifica as linhas de migração de declarações e inventário de munições.

Revision ID: 20261117_merge_heads_declaracoes_municoes
Revises: 20261016_decl_res_data, 20261117_id_municao_sisgcorp_sicovem
"""
from alembic import op


revision = "20261117_merge_heads_declaracoes_municoes"
down_revision = (
    "20261016_decl_res_data",
    "20261117_id_municao_sisgcorp_sicovem",
)
branch_labels = None
depends_on = None


def upgrade():
    # Merge-only migration: as duas linhas já executam suas próprias alterações.
    pass


def downgrade():
    # A reversão apenas reabre os dois heads anteriores; não desfaz dados.
    pass
