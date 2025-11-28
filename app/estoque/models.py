# ============================================================
# MÓDULO: ESTOQUE — Modelos (app/estoque/models.py)
# ============================================================

from app import db
from datetime import datetime
from app.produtos.models import Produto
from app.clientes.models import Cliente
from app.utils.datetime import now_local

class ItemEstoque(db.Model):
    __tablename__ = "estoque_itens"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)

    # Vínculo com a Compra (Rastreabilidade de Entrada)
    compra_item_id = db.Column(db.Integer, db.ForeignKey("compra_item.id"), nullable=True)

    tipo_item = db.Column(db.String(20), nullable=False)
    numero_serie = db.Column(db.String(100), nullable=True)
    lote = db.Column(db.String(50), nullable=True)
    
    # Dados Fiscais e Logísticos
    nota_fiscal = db.Column(db.String(50), nullable=True) 
    data_nf = db.Column(db.Date, nullable=True)
    
    # === NOVOS CAMPOS: GUIA DE TRÂNSITO ===
    guia_transito_file = db.Column(db.String(500), nullable=True) # URL do arquivo no R2
    numero_selo = db.Column(db.String(100), nullable=True)        # Selo de rastreabilidade
    
    numero_embalagem = db.Column(db.String(100), nullable=True, index=True)
    
    quantidade = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default="disponivel", nullable=False)

    data_entrada = db.Column(db.Date, default=lambda: now_local().date())
    observacoes = db.Column(db.Text, nullable=True)

    # Relacionamentos
    produto = db.relationship("Produto", backref="itens_estoque")
    fornecedor = db.relationship("Cliente", back_populates="itens_fornecidos")
    
    # Relacionamento Reverso com Compra
    origem_compra = db.relationship("CompraItem", back_populates="itens_gerados_estoque")

    # Relacionamento com Venda (Saída)
    venda_item = db.relationship(
        "ItemVenda", 
        back_populates="item_estoque",
        uselist=False
    )

    def __repr__(self):
        nome = self.produto.nome if self.produto else "Desconhecido"
        return f"<ItemEstoque {self.id} [{self.tipo_item}] {nome} - {self.status}>"