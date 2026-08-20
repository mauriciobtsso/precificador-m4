"""Associate storefront carts and orders with loja Cliente.

Revision ID: 20260820_storefront_orders_cliente
Revises: eb1852596428
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa


revision = '20260820_storefront_orders_cliente'
down_revision = 'eb1852596428'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'carrinhos',
        sa.Column('cliente_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        'ix_carrinhos_cliente_id',
        'carrinhos',
        ['cliente_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_carrinhos_cliente_id_clientes',
        'carrinhos',
        'clientes',
        ['cliente_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.add_column(
        'pedidos',
        sa.Column('cliente_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        'ix_pedidos_cliente_id',
        'pedidos',
        ['cliente_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_pedidos_cliente_id_clientes',
        'pedidos',
        'clientes',
        ['cliente_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Vincula registros antigos sem depender de dados enviados pelo navegador.
    # O CPF é comparado apenas com dígitos; o e-mail é fallback.
    op.execute(sa.text("""
        UPDATE pedidos AS p
           SET cliente_id = c.id
          FROM clientes AS c
         WHERE p.cliente_id IS NULL
           AND (
                (
                    NULLIF(regexp_replace(COALESCE(p.documento, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                    AND regexp_replace(COALESCE(p.documento, ''), '[^0-9]', '', 'g') =
                        regexp_replace(COALESCE(c.documento, ''), '[^0-9]', '', 'g')
                )
                OR (
                    NULLIF(lower(trim(COALESCE(p.email_cliente, ''))), '') IS NOT NULL
                    AND lower(trim(p.email_cliente)) = lower(trim(COALESCE(c.email_login, '')))
                )
           )
    """))


def downgrade():
    op.drop_constraint(
        'fk_pedidos_cliente_id_clientes',
        'pedidos',
        type_='foreignkey',
    )
    op.drop_index('ix_pedidos_cliente_id', table_name='pedidos')
    op.drop_column('pedidos', 'cliente_id')

    op.drop_constraint(
        'fk_carrinhos_cliente_id_clientes',
        'carrinhos',
        type_='foreignkey',
    )
    op.drop_index('ix_carrinhos_cliente_id', table_name='carrinhos')
    op.drop_column('carrinhos', 'cliente_id')


# A associação permanece nullable para preservar carrinhos e pedidos históricos.
