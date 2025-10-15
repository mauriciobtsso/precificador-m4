"""add indexes to notificacao"""

from alembic import op
import sqlalchemy as sa

# Revisão atual
revision = "c99999999999"
down_revision = "c73fbe572f2e"
branch_labels = None
depends_on = None


def upgrade():
    # Índice composto para filtros comuns
    op.create_index(
        "ix_notif_cliente_tipo_status_data",
        "notificacao",
        ["cliente_id", "tipo", "status", "data_envio"],
        unique=False
    )

    # Índice funcional para verificação de duplicidades diárias
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_notif_cliente_tipo_msg_data_dia
        ON notificacao (cliente_id, tipo, mensagem, (date(data_envio)));
    """)


def downgrade():
    op.drop_index("ix_notif_cliente_tipo_status_data", table_name="notificacao")
    op.execute("DROP INDEX IF EXISTS ix_notif_cliente_tipo_msg_data_dia;")
