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

    # === CORREÇÃO DO ERRO FATAL (NoForeignKeysError) ===
    # Este campo cria o elo físico com o item da nota fiscal de compra
    compra_item_id = db.Column(db.Integer, db.ForeignKey("compra_item.id"), nullable=True)

    tipo_item = db.Column(db.String(20), nullable=False)  # arma, municao, pce, nao_controlado
    numero_serie = db.Column(db.String(100), nullable=True)
    lote = db.Column(db.String(50), nullable=True)
    
    # Rastreabilidade da Entrada
    nota_fiscal = db.Column(db.String(50), nullable=True) 
    data_nf = db.Column(db.Date, nullable=True)
    
    # Campo para o scanner/logística
    numero_embalagem = db.Column(db.String(100), nullable=True, index=True)
    
    quantidade = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default="disponivel", nullable=False)

    data_entrada = db.Column(db.Date, default=lambda: now_local().date())

    observacoes = db.Column(db.Text, nullable=True)

    # Relacionamentos
    produto = db.relationship("Produto", backref="itens_estoque")
    fornecedor = db.relationship("Cliente", back_populates="itens_fornecidos")
    
    # Relacionamento Reverso com Compra (Funciona graças ao compra_item_id acima)
    origem_compra = db.relationship("CompraItem", back_populates="itens_gerados_estoque")

    # Relacionamento com Venda
    # CORREÇÃO DO WARNING: Usamos back_populates para sincronizar com app/vendas/models.py
    venda_item = db.relationship(
        "ItemVenda", 
        back_populates="item_estoque", # Sincroniza com o lado da Venda
        uselist=False
    )

    def __repr__(self):
        nome = self.produto.nome if self.produto else "Desconhecido"
        return f"<ItemEstoque {self.id} [{self.tipo_item}] {nome} - {self.status}>"