# =======================================================
# MÓDULO: app/vendas/models.py
# Estrutura revisada - compatível com relatórios TDVendas
# =======================================================

from datetime import datetime, date
from app.extensions import db


# =========================
# VENDA
# =========================
class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)

    # --- Relacionamento principal ---
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)

    # --- Identificação / relacionamento ---
    vendedor = db.Column(db.String(100))
    caixa = db.Column(db.String(100))

    # --- Datas principais ---
    data_abertura = db.Column(db.DateTime)
    data_fechamento = db.Column(db.DateTime)
    data_quitacao = db.Column(db.DateTime)
    data_cancelamento = db.Column(db.DateTime)

    # --- Status ---
    status = db.Column(db.String(50))
    status_financeiro = db.Column(db.String(50))
    teve_devolucao = db.Column(db.Boolean, default=False)

    # --- Dados financeiros ---
    valor_total = db.Column(db.Float, default=0.0)
    desconto_valor = db.Column(db.Float, default=0.0)
    desconto_percentual = db.Column(db.Float, default=0.0)
    valor_recebido = db.Column(db.Float, default=0.0)
    valor_faltante = db.Column(db.Float, default=0.0)

    # --- Parcelamento / Crediário ---
    crediario = db.Column(db.Boolean, default=False)
    parcelas_qtd = db.Column(db.Integer)
    parcelas_primeiro_vencimento = db.Column(db.Date)
    parcelas_ultimo_vencimento = db.Column(db.Date)

    # --- Dados fiscais ---
    nf_data = db.Column(db.Date)
    nf_numero = db.Column(db.String(50))
    nf_valor = db.Column(db.Float)

    # --- Dados auxiliares de cliente (para importações históricas) ---
    cliente_nome = db.Column(db.String(200))
    documento_cliente = db.Column(db.String(50))
    tipo_pessoa = db.Column(db.String(20))

    # --- Quantitativo geral ---
    qtd_total_itens = db.Column(db.Integer, default=0)

    # --- Controle interno ---
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()
    )

    # --- Relacionamentos ---
    itens = db.relationship("ItemVenda", backref="venda", lazy=True, cascade="all, delete-orphan")
    cliente = db.relationship("Cliente", back_populates="vendas")

    # --- Métodos auxiliares ---
    def calcular_totais(self):
        """Recalcula totais e descontos com base nos itens."""
        if not self.itens:
            self.valor_total = 0
            self.qtd_total_itens = 0
            return

        total = sum(item.valor_total for item in self.itens)
        self.qtd_total_itens = sum(item.quantidade for item in self.itens)
        self.valor_total = round(total, 2)

    def __repr__(self):
        return f"<Venda {self.id} | Cliente={self.cliente_nome or self.cliente_id}>"

    def to_dict(self):
        """Conversão simplificada para API / JSON"""
        return {
            "id": self.id,
            "cliente": self.cliente_nome,
            "documento": self.documento_cliente,
            "vendedor": self.vendedor,
            "status": self.status,
            "status_financeiro": self.status_financeiro,
            "valor_total": float(self.valor_total or 0),
            "data_abertura": self.data_abertura.strftime("%Y-%m-%d %H:%M") if self.data_abertura else None,
        }


# =========================
# ITEM DE VENDA
# =========================
class ItemVenda(db.Model):
    __tablename__ = "itens_venda"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)

    produto_nome = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(100))
    quantidade = db.Column(db.Integer, default=1)
    valor_unitario = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)

    # Campos opcionais (futuros aprimoramentos)
    sku = db.Column(db.String(50))
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True)

    def __repr__(self):
        return f"<ItemVenda {self.id} - {self.produto_nome} ({self.quantidade}x)>"

    def to_dict(self):
        return {
            "produto": self.produto_nome,
            "categoria": self.categoria,
            "quantidade": self.quantidade,
            "valor_unitario": float(self.valor_unitario or 0),
            "valor_total": float(self.valor_total or 0),
        }
