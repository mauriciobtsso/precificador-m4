# =======================================================
# MÓDULO: app/vendas/models.py
# Estrutura revisada - Vendas 2.0
# =======================================================

from datetime import datetime, date
from decimal import Decimal  # <--- ADICIONADO PARA CORREÇÃO DE ERRO
from app.extensions import db

# =========================
# VENDA (PEDIDO)
# =========================
class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    vendedor = db.Column(db.String(100))
    caixa = db.Column(db.String(100))

    # Datas
    data_abertura = db.Column(db.DateTime, default=datetime.now)
    data_fechamento = db.Column(db.DateTime)
    data_quitacao = db.Column(db.DateTime)
    data_cancelamento = db.Column(db.DateTime)

    # Status e Workflow
    status = db.Column(db.String(50)) 
    status_financeiro = db.Column(db.String(50))
    tipo_processo = db.Column(db.String(20), default='livre') # arma, municao, livre
    etapa = db.Column(db.String(50), default="RASCUNHO", index=True)
    
    teve_devolucao = db.Column(db.Boolean, default=False)
    data_entrega_efetiva = db.Column(db.DateTime, nullable=True)
    retirado_por = db.Column(db.String(150), nullable=True)

    # Financeiro (Numeric para precisão monetária)
    valor_total = db.Column(db.Numeric(10, 2), default=0.0)
    desconto_valor = db.Column(db.Numeric(10, 2), default=0.0)
    desconto_percentual = db.Column(db.Float, default=0.0)
    valor_recebido = db.Column(db.Numeric(10, 2), default=0.0)
    valor_faltante = db.Column(db.Numeric(10, 2), default=0.0)

    # Crediário
    crediario = db.Column(db.Boolean, default=False)
    parcelas_qtd = db.Column(db.Integer)
    parcelas_primeiro_vencimento = db.Column(db.Date)
    parcelas_ultimo_vencimento = db.Column(db.Date)

    # Fiscal
    nf_data = db.Column(db.Date)
    nf_numero = db.Column(db.String(50))
    nf_valor = db.Column(db.Numeric(10, 2))

    # Snapshot Cliente
    cliente_nome = db.Column(db.String(200))
    documento_cliente = db.Column(db.String(50))
    tipo_pessoa = db.Column(db.String(20))

    qtd_total_itens = db.Column(db.Integer, default=0)
    observacoes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    # Relacionamentos
    itens = db.relationship("ItemVenda", backref="venda", lazy=True, cascade="all, delete-orphan")
    cliente = db.relationship("Cliente", back_populates="vendas")
    anexos = db.relationship("VendaAnexo", backref="venda", lazy="dynamic", cascade="all, delete-orphan")

    def calcular_totais(self):
        """
        Recalcula totais garantindo precisão Decimal para evitar erros com Float.
        """
        if not self.itens:
            self.valor_total = Decimal('0.00')
            self.qtd_total_itens = 0
            self.valor_faltante = Decimal('0.00')
            return
        
        # Soma segura usando Decimal como base
        # Converte cada valor_total de item para Decimal se já não for
        total = sum((item.valor_total for item in self.itens), Decimal('0.00'))
        
        self.qtd_total_itens = sum(item.quantidade for item in self.itens)
        self.valor_total = total
        
        # Garante que desconto e recebido sejam Decimal antes de subtrair
        desc = self.desconto_valor
        if desc is None: desc = Decimal('0.00')
        elif not isinstance(desc, Decimal): desc = Decimal(str(desc))
            
        rec = self.valor_recebido
        if rec is None: rec = Decimal('0.00')
        elif not isinstance(rec, Decimal): rec = Decimal(str(rec))

        self.valor_faltante = self.valor_total - desc - rec

    def __repr__(self):
        return f"<Venda {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente_nome,
            "status": self.status,
            "valor_total": float(self.valor_total or 0)
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
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    sku = db.Column(db.String(50))
    
    # Rastreabilidade
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True)
    item_estoque_id = db.Column(db.Integer, db.ForeignKey("estoque_itens.id"), nullable=True)
    arma_cliente_id = db.Column(db.Integer, db.ForeignKey("armas.id"), nullable=True)

    produto = db.relationship("Produto")
    item_estoque = db.relationship("ItemEstoque") 
    arma_cliente = db.relationship("Arma", foreign_keys=[arma_cliente_id])

    def __repr__(self):
        return f"<ItemVenda {self.id} - {self.produto_nome}>"

# =========================
# ANEXOS
# =========================
class VendaAnexo(db.Model):
    __tablename__ = "vendas_anexos"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)
    tipo_documento = db.Column(db.String(50), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    url_arquivo = db.Column(db.String(500), nullable=False)
    metadados = db.Column(db.JSON, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    enviado_por = db.Column(db.String(100))