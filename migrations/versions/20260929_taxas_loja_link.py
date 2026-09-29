"""Cria taxas independentes para o parcelamento da loja.

Revision ID: 20260929_taxas_link
Revises: b7c4d91f2a10
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_taxas_link"
down_revision = "b7c4d91f2a10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "taxas_loja_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero_parcelas", sa.Integer(), nullable=False),
        sa.Column("juros", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "numero_parcelas",
            name="uq_taxas_loja_link_numero_parcelas",
        ),
    )
    # Inicializa a tabela nova com as taxas atuais, sem alterar a tabela usada
    # pelos fluxos internos. Em caso de duplicidade legada, mantém o menor id.
    bind = op.get_bind()
    if sa.inspect(bind).has_table("taxas"):
        existentes = bind.execute(
            sa.text(
                "SELECT id, numero_parcelas, juros "
                "FROM taxas ORDER BY numero_parcelas ASC, id ASC"
            )
        )
        parcelas_importadas = set()
        for row in existentes:
            numero = row.numero_parcelas
            if numero is None or numero in parcelas_importadas:
                continue
            parcelas_importadas.add(numero)
            bind.execute(
                sa.text(
                    "INSERT INTO taxas_loja_link (numero_parcelas, juros) "
                    "VALUES (:numero_parcelas, :juros)"
                ),
                {
                    "numero_parcelas": numero,
                    "juros": float(row.juros or 0),
                },
            )


def downgrade():
    op.drop_table("taxas_loja_link")
