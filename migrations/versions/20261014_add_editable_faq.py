"""Create editable storefront FAQ entries and migrate current content.

Revision ID: 20261014_editable_faq
Revises: 20261007_pf_pj_localidade
"""
from alembic import op
import sqlalchemy as sa


revision = "20261014_editable_faq"
down_revision = "20261007_pf_pj_localidade"
branch_labels = None
depends_on = None


_INITIAL_FAQS = [
    {
        "pergunta": "Preciso de porte para comprar uma arma?",
        "resposta": (
            "Não. O porte e a autorização de aquisição são processos diferentes. "
            "Para adquirir uma arma de uso permitido, é necessária autorização prévia "
            "da Polícia Federal. Depois da compra, é preciso fazer o registro. A PF "
            "informa que a retirada depende da emissão do CRAF e da guia de trânsito."
        ),
        "link_texto": "Consulte o serviço oficial da PF",
        "link_url": "https://www.gov.br/pf/pt-br/assuntos/carta-de-servicos/armas/adquirir-arma-de-fogo",
        "ordem": 1,
        "publicada": True,
    },
    {
        "pergunta": "Quais são os requisitos básicos para iniciar a aquisição de uma arma?",
        "resposta": (
            "Para a categoria cidadão, a regra geral exige idade mínima de 25 anos, "
            "salvo exceções legais. A PF também analisa a efetiva necessidade, a "
            "idoneidade, a ocupação lícita, a residência, a capacidade técnica e a "
            "aptidão psicológica. A lista de documentos e o resultado dependem da análise oficial."
        ),
        "link_texto": "Confira os requisitos e etapas na PF",
        "link_url": "https://www.gov.br/pf/pt-br/assuntos/carta-de-servicos/armas/adquirir-arma-de-fogo",
        "ordem": 2,
        "publicada": True,
    },
    {
        "pergunta": "Preciso de porte para comprar munição?",
        "resposta": (
            "Não. Para munição de uso permitido, a norma da PF prevê CRAF válido do "
            "proprietário e munição do calibre correspondente à arma registrada. "
            "A quantidade e os documentos adicionais seguem as regras atuais e podem "
            "variar conforme a categoria."
        ),
        "link_texto": "Consulte a Instrução Normativa da PF",
        "link_url": "https://www.gov.br/pf/pt-br/assuntos/armas/normativos/in2012021atualizadadgpf.pdf",
        "ordem": 3,
        "publicada": True,
    },
    {
        "pergunta": "Que documentos devo levar para comprar munição?",
        "resposta": (
            "Leve documento de identificação e o CRAF válido da arma registrada em seu nome. "
            "Atiradores devem levar também o CR. Militares devem levar a identidade militar. "
            "Policiais e outras categorias devem levar a identificação funcional. A equipe "
            "confirma os documentos aplicáveis ao seu caso antes da venda."
        ),
        "link_texto": None,
        "link_url": None,
        "ordem": 4,
        "publicada": True,
    },
    {
        "pergunta": "A M4 Tática envia munições ou permite retirada por outra pessoa?",
        "resposta": (
            "Não. Pela política da M4 Tática, munições e cartuchos são vendidos e retirados "
            "somente na loja física. A retirada deve ser feita pelo próprio comprador, "
            "após a conferência da documentação."
        ),
        "link_texto": None,
        "link_url": None,
        "ordem": 5,
        "publicada": True,
    },
    {
        "pergunta": "Quais calibres são de uso restrito?",
        "resposta": (
            "A classificação depende das características da arma e das normas vigentes. "
            "As regras foram alteradas em 2025. Por isso, não use listas antigas como referência. "
            "Envie o modelo exato e sua categoria à equipe para conferência. A página de "
            "legislação da PF reúne os atos atuais."
        ),
        "link_texto": "Página de legislação da PF",
        "link_url": "https://www.gov.br/pf/pt-br/assuntos/armas/normativos/legislacao",
        "ordem": 6,
        "publicada": True,
    },
    {
        "pergunta": "Que comprovante de endereço posso apresentar?",
        "resposta": (
            "A página de serviço da PF lista comprovante recente de residência e orienta sobre "
            "documentos adicionais quando a conta está em nome de cônjuge, companheiro ou terceiro. "
            "A mesma página informa o prazo de emissão aceito. Além disso, as certidões criminais "
            "podem abranger os locais de domicílio dos últimos cinco anos. São exigências diferentes."
        ),
        "link_texto": "Confira o checklist oficial antes de enviar o pedido",
        "link_url": "https://www.gov.br/pf/pt-br/assuntos/carta-de-servicos/armas/adquirir-arma-de-fogo",
        "ordem": 7,
        "publicada": True,
    },
    {
        "pergunta": "Quanto tempo leva a análise da Polícia Federal?",
        "resposta": (
            "O prazo pode variar. A página de serviço da PF informa uma estimativa de até 30 dias "
            "para análise. Acompanhe o pedido pelos canais oficiais. A M4 Tática não controla a fila "
            "nem pode garantir a data de decisão."
        ),
        "link_texto": None,
        "link_url": None,
        "ordem": 8,
        "publicada": True,
    },
    {
        "pergunta": "Qual é o valor do processo de posse e como posso parcelar?",
        "resposta": (
            "O valor informado pela M4 Tática é R$ 1.600,00 à vista ou 10 parcelas de R$ 184,33 "
            "no cartão de crédito. Confirme com a equipe se as condições continuam vigentes e o que "
            "está incluído. Para outros produtos, peça uma simulação atualizada de parcelamento "
            "pelo WhatsApp."
        ),
        "link_texto": None,
        "link_url": None,
        "ordem": 9,
        "publicada": True,
    },
]


def upgrade():
    op.create_table(
        "loja_perguntas_frequentes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pergunta", sa.String(length=300), nullable=False),
        sa.Column("resposta", sa.Text(), nullable=False),
        sa.Column("link_texto", sa.String(length=200), nullable=True),
        sa.Column("link_url", sa.String(length=1000), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("publicada", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criada_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizada_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_loja_faq_publicada_ordem",
        "loja_perguntas_frequentes",
        ["publicada", "ordem"],
        unique=False,
    )

    faq_table = sa.table(
        "loja_perguntas_frequentes",
        sa.column("pergunta", sa.String()),
        sa.column("resposta", sa.Text()),
        sa.column("link_texto", sa.String()),
        sa.column("link_url", sa.String()),
        sa.column("ordem", sa.Integer()),
        sa.column("publicada", sa.Boolean()),
    )
    op.bulk_insert(faq_table, _INITIAL_FAQS)


def downgrade():
    op.drop_index("ix_loja_faq_publicada_ordem", table_name="loja_perguntas_frequentes")
    op.drop_table("loja_perguntas_frequentes")
