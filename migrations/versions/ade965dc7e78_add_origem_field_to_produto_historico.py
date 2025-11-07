"""Add origem field to produto_historico

Revision ID: ade965dc7e78
Revises: ec83b3f1622f
Create Date: 2025-11-07 17:22:26.335880
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ade965dc7e78'
down_revision = 'ec83b3f1622f'
branch_labels = None
depends_on = None


def upgrade():
    # =====================================================
    # Ajustes em estoque_itens (mantidos da autogeração)
    # =====================================================
    with op.batch_alter_table('estoque_itens', schema=None) as batch_op:
        batch_op.alter_column(
            'tipo_item',
            existing_type=sa.VARCHAR(length=50),
            type_=sa.String(length=20),
            nullable=False
        )
        batch_op.alter_column(
            'lote',
            existing_type=sa.VARCHAR(length=100),
            type_=sa.String(length=50),
            existing_nullable=True
        )
        batch_op.alter_column(
            'numero_embalagem',
            existing_type=sa.VARCHAR(length=100),
            type_=sa.String(length=50),
            existing_nullable=True
        )
        batch_op.alter_column(
            'quantidade',
            existing_type=sa.INTEGER(),
            nullable=True
        )
        batch_op.alter_column(
            'status',
            existing_type=sa.VARCHAR(length=50),
            type_=sa.String(length=30),
            nullable=False
        )
        batch_op.alter_column(
            'data_entrada',
            existing_type=postgresql.TIMESTAMP(timezone=True),
            type_=sa.Date(),
            existing_nullable=True
        )
        batch_op.drop_constraint(
            batch_op.f('estoque_itens_numero_serie_key'),
            type_='unique'
        )

    # =====================================================
    # Adição do campo 'origem' em produto_historico
    # =====================================================
    with op.batch_alter_table('produto_historico', schema=None) as batch_op:
        # Cria a coluna com valor padrão temporário
        batch_op.add_column(
            sa.Column('origem', sa.String(length=20), nullable=True, server_default='manual')
        )

    # Preenche registros antigos com 'manual'
    op.execute("UPDATE produto_historico SET origem = 'manual' WHERE origem IS NULL;")

    # Remove o default e aplica NOT NULL
    with op.batch_alter_table('produto_historico', schema=None) as batch_op:
        batch_op.alter_column('origem', nullable=False, server_default=None)


def downgrade():
    # =====================================================
    # Remoção do campo 'origem' e reversão de estoque_itens
    # =====================================================
    with op.batch_alter_table('produto_historico', schema=None) as batch_op:
        batch_op.drop_column('origem')

    with op.batch_alter_table('estoque_itens', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            batch_op.f('estoque_itens_numero_serie_key'),
            ['numero_serie'],
            postgresql_nulls_not_distinct=False
        )
        batch_op.alter_column(
            'data_entrada',
            existing_type=sa.Date(),
            type_=postgresql.TIMESTAMP(timezone=True),
            existing_nullable=True
        )
        batch_op.alter_column(
            'status',
            existing_type=sa.String(length=30),
            type_=sa.VARCHAR(length=50),
            nullable=True
        )
        batch_op.alter_column(
            'quantidade',
            existing_type=sa.INTEGER(),
            nullable=False
        )
        batch_op.alter_column(
            'numero_embalagem',
            existing_type=sa.String(length=50),
            type_=sa.VARCHAR(length=100),
            existing_nullable=True
        )
        batch_op.alter_column(
            'lote',
            existing_type=sa.String(length=50),
            type_=sa.VARCHAR(length=100),
            existing_nullable=True
        )
        batch_op.alter_column(
            'tipo_item',
            existing_type=sa.String(length=20),
            type_=sa.VARCHAR(length=50),
            nullable=True
        )
