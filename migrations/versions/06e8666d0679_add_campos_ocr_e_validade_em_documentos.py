"""add campos OCR e validade em documentos

Revision ID: 8d3a42c9a6f4
Revises: f07a79e2c320
Create Date: 2025-10-04 09:40:00 -03:00
"""

from alembic import op
import sqlalchemy as sa


# Revisões
revision = "8d3a42c9a6f4"
down_revision = 'f07a79e2c320'
branch_labels = None
depends_on = None


def upgrade():
    # Novos campos para OCR e validade
    with op.batch_alter_table("documentos") as batch_op:
        batch_op.add_column(sa.Column("categoria", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("emissor", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("numero_documento", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("data_emissao", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("data_validade", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("validade_indeterminada", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("observacoes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")))

        # Índices para otimizar buscas
        batch_op.create_index("ix_documentos_categoria", ["categoria"], unique=False)
        batch_op.create_index("ix_documentos_numero_documento", ["numero_documento"], unique=False)


def downgrade():
    with op.batch_alter_table("documentos") as batch_op:
        batch_op.drop_index("ix_documentos_categoria")
        batch_op.drop_index("ix_documentos_numero_documento")
        batch_op.drop_column("categoria")
        batch_op.drop_column("emissor")
        batch_op.drop_column("numero_documento")
        batch_op.drop_column("data_emissao")
        batch_op.drop_column("data_validade")
        batch_op.drop_column("validade_indeterminada")
        batch_op.drop_column("observacoes")
        batch_op.drop_column("created_at")
        batch_op.drop_column("updated_at")
