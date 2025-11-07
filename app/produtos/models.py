# ======================
# MODELO — PRODUTO
# ======================

from app import db
from sqlalchemy import func
from datetime import datetime
import pytz
from flask_login import current_user

# Importações auxiliares
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto,
    CalibreProduto,
    TipoProduto,
    FuncionamentoProduto,
)

# ======================================================
# FUSO HORÁRIO PADRÃO LOCAL
# ======================================================
TZ_FORTALEZA = pytz.timezone("America/Fortaleza")

def now_local():
    """Retorna o horário atual no fuso de Teresina (UTC-3)."""
    return datetime.now(TZ_FORTALEZA)


# ======================================================
# MODELO PRINCIPAL: PRODUTO
# ======================================================
class Produto(db.Model):
    __tablename__ = "produtos"

    foto_url = db.Column(db.String(512), nullable=True)
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)  # SKU
    nome = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)

    # ============================
    # RELACIONAMENTOS (FKs)
    # ============================
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria_produto.id"))
    categoria = db.relationship("CategoriaProduto", backref="produtos")

    marca_id = db.Column(db.Integer, db.ForeignKey("marca_produto.id"), nullable=True)
    marca_rel = db.relationship("MarcaProduto", backref="produtos")

    calibre_id = db.Column(db.Integer, db.ForeignKey("calibre_produto.id"), nullable=True)
    calibre_rel = db.relationship("CalibreProduto", backref="produtos")

    tipo_id = db.Column(db.Integer, db.ForeignKey("tipo_produto.id"), nullable=True)
    tipo_rel = db.relationship("TipoProduto", backref="produtos")

    funcionamento_id = db.Column(db.Integer, db.ForeignKey("funcionamento_produto.id"), nullable=True)
    funcionamento_rel = db.relationship("FuncionamentoProduto", backref="produtos")

    # ============================
    # CAMPOS ANTIGOS (LEGADO)
    # ============================
    tipo = db.Column(db.String(80), nullable=True)
    marca = db.Column(db.String(80), nullable=True)
    calibre = db.Column(db.String(50), nullable=True)

    # ============================
    # CUSTOS E IMPOSTOS
    # ============================
    preco_fornecedor = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    desconto_fornecedor = db.Column(db.Numeric(5, 2), nullable=True, default=0)
    frete = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    margem = db.Column(db.Numeric(5, 2), nullable=True, default=0)
    ipi = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    ipi_tipo = db.Column(db.String(10), nullable=True, default="%")  # "%", "%_dentro", "R$"
    difal = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    imposto_venda = db.Column(db.Numeric(10, 2), nullable=True, default=0)

    # ============================
    # CÁLCULOS DERIVADOS
    # ============================
    custo_total = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    preco_a_vista = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    lucro_liquido_real = db.Column(db.Numeric(12, 2), nullable=True, default=0)

    # ============================
    # OBJETIVOS
    # ============================
    lucro_alvo = db.Column(db.Numeric(12, 2), nullable=True)
    preco_final = db.Column(db.Numeric(12, 2), nullable=True)

    # ============================
    # AUDITORIA
    # ============================
    criado_em = db.Column(db.DateTime(timezone=True), default=now_local)
    atualizado_em = db.Column(db.DateTime(timezone=True), onupdate=now_local, default=now_local)

    # ============================
    # RELAÇÃO COM HISTÓRICO
    # ============================
    historicos = db.relationship(
        "ProdutoHistorico",
        back_populates="produto",
        cascade="all, delete-orphan",
        lazy=True,
    )

    # ======================
    # MÉTODOS AUXILIARES
    # ======================
    def calcular_precos(self):
        """Cálculo completo de custo total, preço sugerido e lucro líquido."""
        preco_fornecedor = float(self.preco_fornecedor or 0)
        desconto = float(self.desconto_fornecedor or 0)
        frete = float(self.frete or 0)
        margem = float(self.margem or 0)
        imposto_venda = float(self.imposto_venda or 0)
        difal = float(self.difal or 0)
        ipi = float(self.ipi or 0)
        ipi_tipo = (self.ipi_tipo or "%").strip()

        base = preco_fornecedor * (1 - (desconto / 100))
        if ipi_tipo == "%_dentro":
            base_sem_ipi = base / (1 + (ipi / 100))
            valor_ipi = base - base_sem_ipi
        elif ipi_tipo == "%":
            valor_ipi = base * (ipi / 100)
        else:
            valor_ipi = ipi

        valor_difal = (base - valor_ipi + frete) * (difal / 100)
        custo_total = base + valor_difal + frete

        preco_final = float(self.preco_final or 0)
        lucro_alvo = float(self.lucro_alvo or 0)
        if preco_final <= 0:
            if lucro_alvo > 0:
                preco_final = (custo_total + lucro_alvo) / (1 - (imposto_venda / 100))
            elif margem > 0:
                preco_final = custo_total / (1 - (margem / 100))
            else:
                preco_final = custo_total

        imposto_venda_valor = preco_final * (imposto_venda / 100)
        lucro_liquido = preco_final - custo_total - imposto_venda_valor

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


# ======================================================
# MODELO: HISTÓRICO DE ALTERAÇÕES DE PRODUTO
# ======================================================
class ProdutoHistorico(db.Model):
    __tablename__ = "produto_historico"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(
        db.Integer,
        db.ForeignKey("produtos.id", ondelete="CASCADE"),
        nullable=False,
    )
    campo = db.Column(db.String(100), nullable=False)
    valor_antigo = db.Column(db.Text)
    valor_novo = db.Column(db.Text)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),  # ✅ referência correta para tabela 'users'
        nullable=True,
    )
    usuario_nome = db.Column(db.String(120))
    data_modificacao = db.Column(db.DateTime(timezone=True), default=now_local)
    origem = db.Column(db.String(20), nullable=False, default="manual")  # ← NOVO CAMPO

    produto = db.relationship("Produto", back_populates="historicos")

    def __repr__(self):
        return f"<Histórico Produto {self.produto_id} ({self.campo})>"
