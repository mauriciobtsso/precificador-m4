"""Seed editable declaration templates.

Revision ID: 20261015_declaracoes
Revises: 20261015_expand_certidoes
"""
from alembic import op
import sqlalchemy as sa

revision = "20261015_declaracoes"
down_revision = "20261015_expand_certidoes"
branch_labels = None
depends_on = None

_MODELOS = [
    ("Declaração de Residência", "declaracao_residencia", "Eu, <b>{{ cliente.nome }}</b>, inscrito(a) no CPF/CNPJ sob o nº <b>{{ cliente.documento }}</b>, declaro, para os devidos fins, que resido no endereço <b>{{ cliente.endereco_completo }}</b>. Declaro ainda que as informações acima são verdadeiras, estando ciente das responsabilidades legais decorrentes da falsidade desta declaração."),
    ("Declaração de Não Responder a Inquérito Policial", "declaracao_nao_inquerito", "Eu, <b>{{ cliente.nome }}</b>, inscrito(a) no CPF/CNPJ sob o nº <b>{{ cliente.documento }}</b>, declaro, para os devidos fins, que não estou respondendo a inquérito policial, salvo se expressamente informado em documento próprio. Declaro que as informações prestadas são verdadeiras e assumo responsabilidade por seu conteúdo."),
]


def upgrade():
    bind = sa.table("modelos_documento", sa.column("titulo", sa.String()), sa.column("chave", sa.String()), sa.column("conteudo", sa.Text()))
    conn = op.get_bind()
    for titulo, chave, conteudo in _MODELOS:
        if not conn.execute(sa.text("SELECT 1 FROM modelos_documento WHERE chave=:chave"), {"chave": chave}).first():
            op.bulk_insert(bind, [{"titulo": titulo, "chave": chave, "conteudo": conteudo}])


def downgrade():
    op.execute("DELETE FROM modelos_documento WHERE chave IN ('declaracao_residencia', 'declaracao_nao_inquerito')")
