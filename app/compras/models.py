# ============================================================
# MÓDULO: COMPRAS — Modelos de NF e Itens
# ============================================================

from app import db
from datetime import datetime
from decimal import Decimal
import uuid
from app.utils.datetime import now_local

class CompraNF(db.Model):
    __tablename__ = "compra_nf"

    id = db.Column(db.Integer, primary_key=True)
    
    # Vínculo com Pedido
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido_compra.id"), nullable=True)
    pedido = db.relationship("PedidoCompra", backref=db.backref("nfs", lazy=True))

    numero = db.Column(db.String(50))
    chave = db.Column(db.String(200), unique=True, nullable=True, index=True)

    fornecedor = db.Column(db.String(120))
    cnpj_fornecedor = db.Column(db.String(20), nullable=True) # NOVO: CNPJ para vínculo

    data_emissao = db.Column(db.DateTime)
    valor_total = db.Column(db.Numeric(12, 2))
    
    # === DOCS DE TRANSPORTE (GT) ===
    guia_transito_file = db.Column(db.String(500), nullable=True) # URL do R2
    numero_selo = db.Column(db.String(100), nullable=True)

    criado_em = db.Column(db.DateTime, default=now_local)

    itens = db.relationship("CompraItem", back_populates="nf", cascade="all, delete-orphan")

    def calcular_total(self):
        self.valor_total = sum((i.valor_total or 0) for i in self.itens or [])

    def gerar_chave_unica(self):
        if not self.chave:
            self.chave = str(uuid.uuid4())

    def __repr__(self):
        return f"<CompraNF {self.numero}>"


class CompraItem(db.Model):
    __tablename__ = "compra_item"

    id = db.Column(db.Integer, primary_key=True)
    nf_id = db.Column(db.Integer, db.ForeignKey("compra_nf.id", ondelete="CASCADE"))

    # Dados do XML
    descricao = db.Column(db.String(250))
    codigo_produto_xml = db.Column(db.String(50)) # cProd original
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    calibre = db.Column(db.String(50))
    
    lote = db.Column(db.String(100))
    numero_embalagem = db.Column(db.String(100)) # Sugestão do XML
    
    seriais_xml = db.Column(db.Text, nullable=True)

    quantidade = db.Column(db.Numeric(10, 2))
    valor_unitario = db.Column(db.Numeric(10, 2))
    valor_total = db.Column(db.Numeric(12, 2))

    # Vínculo Automático
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True)
    produto_sugerido = db.relationship("Produto")

    nf = db.relationship("CompraNF", back_populates="itens")
    
    # Vínculo com Estoque
    itens_gerados_estoque = db.relationship("ItemEstoque", back_populates="origem_compra", lazy="dynamic")

    def calcular_total(self):
        try:
            q = Decimal(self.quantidade or 0)
            v = Decimal(self.valor_unitario or 0)
            self.valor_total = q * v
        except Exception:
            self.valor_total = Decimal(0)

    def __repr__(self):
        return f"<CompraItem {self.descricao}>"