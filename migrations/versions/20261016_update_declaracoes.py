"""Update seeded declarations to match the supplied forms.

Revision ID: 20261016_update_declaracoes
Revises: 20261015_declaracoes
"""
from alembic import op
import sqlalchemy as sa

revision = "20261016_update_declaracoes"
down_revision = "20261015_declaracoes"
branch_labels = None
depends_on = None


_ANTIGOS = {
    "declaracao_residencia": (
        "Eu, <b>{{ cliente.nome }}</b>, inscrito(a) no CPF/CNPJ sob o nº "
        "<b>{{ cliente.documento }}</b>, declaro, para os devidos fins, que resido no endereço "
        "<b>{{ cliente.endereco_completo }}</b>. Declaro ainda que as informações acima são "
        "verdadeiras, estando ciente das responsabilidades legais decorrentes da falsidade desta declaração."
    ),
    "declaracao_nao_inquerito": (
        "Eu, <b>{{ cliente.nome }}</b>, inscrito(a) no CPF/CNPJ sob o nº "
        "<b>{{ cliente.documento }}</b>, declaro, para os devidos fins, que não estou respondendo "
        "a inquérito policial, salvo se expressamente informado em documento próprio. Declaro que "
        "as informações prestadas são verdadeiras e assumo responsabilidade por seu conteúdo."
    ),
}

_TITULOS_ANTIGOS = {
    "declaracao_residencia": "Declaração de Residência",
    "declaracao_nao_inquerito": "Declaração de Não Responder a Inquérito Policial",
}

_NOVOS = {
    "declaracao_residencia": (
        "Declaração de Residência",
        (
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
        ),
    ),
    "declaracao_nao_inquerito": (
        "Declaração de Inexistência de Inquéritos Policiais ou Processos Criminais",
        (
            "Eu, <b>{{ cliente.nome }}</b>, CPF: <b>{{ cliente.documento }}</b>, residindo em "
            "<b>{{ cliente.endereco_completo }}</b>, declaro, sob as penas da lei, que não "
            "respondo processo criminal e/ou inquérito policial, tanto no Estado de domicílio "
            "quanto nos demais entes federativos, e estou ciente de que, em caso de falsidade "
            "ideológica, ficarei sujeito às sanções prescritas no Código Penal e às demais "
            "cominações legais aplicáveis."
            "<br/><br/>"
            "<i>“Art. 299 —<br/><br/>"
            "Omitir, em documento público ou particular, declaração que nele deveria constar, "
            "ou ele inserir ou fazer inserir declaração falsa ou diversa da que devia ser escrita, "
            "com o fim de prejudicar direito, criar obrigação ou alterar a verdade sobre o fato "
            "juridicamente relevante. Pena: reclusão de 1 (um) a 5 (cinco) anos e multa, se o "
            "documento é público e reclusão de 1 (um) a 3 (três) anos, se o documento é particular.”</i>"
        ),
    ),
}


def _atualizar(chave, titulo_origem, conteudo_origem, titulo_destino, conteudo_destino):
    op.get_bind().execute(
        sa.text(
            "UPDATE modelos_documento "
            "SET titulo = CASE WHEN titulo = :titulo_origem THEN :titulo_destino ELSE titulo END, "
            "conteudo = :conteudo_destino "
            "WHERE chave = :chave AND conteudo = :conteudo_origem"
        ),
        {
            "titulo_origem": titulo_origem,
            "titulo_destino": titulo_destino,
            "conteudo_destino": conteudo_destino,
            "chave": chave,
            "conteudo_origem": conteudo_origem,
        },
    )


def upgrade():
    for chave, conteudo_antigo in _ANTIGOS.items():
        titulo_novo, conteudo_novo = _NOVOS[chave]
        _atualizar(chave, _TITULOS_ANTIGOS[chave], conteudo_antigo, titulo_novo, conteudo_novo)


def downgrade():
    for chave, (titulo_novo, conteudo_novo) in _NOVOS.items():
        _atualizar(
            chave,
            titulo_novo,
            conteudo_novo,
            _TITULOS_ANTIGOS[chave],
            _ANTIGOS[chave],
        )
