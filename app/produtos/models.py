# ======================
# MODELO — PRODUTO
# ======================

from app import db
from sqlalchemy import func
from app.produtos.categorias.models import CategoriaProduto



class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)  # SKU
    nome = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)

    # Relacionamento
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria_produto.id"))
    categoria = db.relationship("CategoriaProduto", backref="produtos")

    # Custos e impostos
    preco_fornecedor = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    desconto_fornecedor = db.Column(db.Numeric(5, 2), nullable=True, default=0)
    frete = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    margem = db.Column(db.Numeric(5, 2), nullable=True, default=0)

    ipi = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    ipi_tipo = db.Column(db.String(10), nullable=True, default="%")  # "%", "%_dentro", "R$"
    difal = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    imposto_venda = db.Column(db.Numeric(10, 2), nullable=True, default=0)

    # Cálculos derivados
    custo_total = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    preco_a_vista = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    lucro_liquido_real = db.Column(db.Numeric(12, 2), nullable=True, default=0)

    # Objetivos
    lucro_alvo = db.Column(db.Numeric(12, 2), nullable=True)
    preco_final = db.Column(db.Numeric(12, 2), nullable=True)

    # Auditoria
    criado_em = db.Column(db.DateTime(timezone=True), server_default=func.now())
    atualizado_em = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    # ======================
    # MÉTODOS AUXILIARES
    # ======================

    def calcular_precos(self):
        """
        Realiza o cálculo completo de custo total, preço sugerido e lucro líquido.
        """
        preco_fornecedor = float(self.preco_fornecedor or 0)
        desconto = float(self.desconto_fornecedor or 0)
        frete = float(self.frete or 0)
        margem = float(self.margem or 0)
        imposto_venda = float(self.imposto_venda or 0)
        difal = float(self.difal or 0)
        ipi = float(self.ipi or 0)
        ipi_tipo = (self.ipi_tipo or "%").strip()

        # 1. Desconto sobre o fornecedor
        base = preco_fornecedor * (1 - (desconto / 100))

        # 2. IPI — considerar embutido, por fora ou fixo
        if ipi_tipo == "%_dentro":
            base_sem_ipi = base / (1 + (ipi / 100))
            valor_ipi = base - base_sem_ipi
        elif ipi_tipo == "%":
            valor_ipi = base * (ipi / 100)
        else:
            valor_ipi = ipi

        # 3. DIFAL
        valor_difal = (base - valor_ipi + frete) * (difal / 100)

        # 4. Custo total (inclui frete)
        custo_total = base + valor_difal + frete

        # 5. Preço sugerido
        preco_final = float(self.preco_final or 0)
        lucro_alvo = float(self.lucro_alvo or 0)
        if preco_final <= 0:
            if lucro_alvo > 0:
                preco_final = (custo_total + lucro_alvo) / (1 - (imposto_venda / 100))
            elif margem > 0:
                preco_final = custo_total / (1 - (margem / 100))
            else:
                preco_final = custo_total

        # 6. Imposto sobre a venda e lucro líquido
        imposto_venda_valor = preco_final * (imposto_venda / 100)
        lucro_liquido = preco_final - custo_total - imposto_venda_valor

        # 7. Atualiza campos persistentes
        self.custo_total = round(custo_total, 2)
        self.preco_a_vista = round(preco_final, 2)
        self.lucro_liquido_real = round(lucro_liquido, 2)

        return {
            "custo_total": self.custo_total,
            "preco_a_vista": self.preco_a_vista,
            "lucro_liquido_real": self.lucro_liquido_real,
        }

    def __repr__(self):
        return f"<Produto {self.codigo} - {self.nome}>"
