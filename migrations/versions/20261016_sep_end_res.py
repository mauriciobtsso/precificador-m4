"""Separate declarant and customer residence addresses in the default declaration.

Revision ID: 20261016_sep_end_res
Revises: 20261016_update_declaracoes
"""
from alembic import op
import sqlalchemy as sa

revision = "20261016_sep_end_res"
down_revision = "20261016_update_declaracoes"
branch_labels = None
depends_on = None

_CHAVE = "declaracao_residencia"
_ANTIGO = (
    "Eu, <b>{{ proprietario.nome }}</b>, inscrito(a) no CPF sob o nº "
    "<b>{{ proprietario.documento }}</b> e portador(a) do RG nº "
    "<b>{{ proprietario.rg }}</b> <b>{{ proprietario.rg_emissor }}</b>, "
    "residente e domiciliado(a) no endereço <b>{{ proprietario.endereco_completo }}</b>,"
    "<br/><br/>"
    "DECLARO, sob as penas da lei e junto à Polícia Federal (SINARM), que o(a) Sr.(a) "
    "<b>{{ cliente.nome }}</b>, inscrito(a) no CPF sob o nº <b>{{ cliente.documento }}</b>, "
    "reside de forma fixa e permanente no endereço acima citado."
    "<br/><br/>"
    "Declaro, ainda, que o vínculo que possuo com o requerente é o de "
    "<b>{{ declaracao.vinculo }}</b>, sendo eu o(a) titular do imóvel e das contas "
    "de consumo atreladas ao referido endereço."
    "<br/><br/>"
    "Por ser a expressão da verdade e ciente das responsabilidades civis e penais "
    "decorrentes de declaração falsa, firmo a presente."
)
_NOVO = (
    "Eu, <b>{{ proprietario.nome }}</b>, inscrito(a) no CPF sob o nº "
    "<b>{{ proprietario.documento }}</b> e portador(a) do RG nº "
    "<b>{{ proprietario.rg }}</b> <b>{{ proprietario.rg_emissor }}</b>, "
    "residente e domiciliado(a) no endereço <b>{{ proprietario.endereco_completo }}</b>,"
    "<br/><br/>"
    "DECLARO, sob as penas da lei e junto à Polícia Federal (SINARM), que o(a) Sr.(a) "
    "<b>{{ cliente.nome }}</b>, inscrito(a) no CPF sob o nº <b>{{ cliente.documento }}</b>, "
    "reside de forma fixa e permanente no endereço <b>{{ cliente.endereco_completo }}</b>."
    "<br/><br/>"
    "Declaro, ainda, que o vínculo que possuo com o requerente é o de "
    "<b>{{ declaracao.vinculo }}</b>."
    "<br/><br/>"
    "Por ser a expressão da verdade e ciente das responsabilidades civis e penais "
    "decorrentes de declaração falsa, firmo a presente."
)


def _atualizar(conteudo_origem, conteudo_destino):
    op.get_bind().execute(
        sa.text(
            "UPDATE modelos_documento SET conteudo = :conteudo_destino "
            "WHERE chave = :chave AND conteudo = :conteudo_origem"
        ),
        {
            "chave": _CHAVE,
            "conteudo_origem": conteudo_origem,
            "conteudo_destino": conteudo_destino,
        },
    )


def upgrade():
    _atualizar(_ANTIGO, _NOVO)


def downgrade():
    _atualizar(_NOVO, _ANTIGO)
