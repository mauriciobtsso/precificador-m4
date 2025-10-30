from app import db
from datetime import datetime

class ItemEstoque(db.Model):
    __tablename__ = 'estoque_itens'

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    produto = db.relationship('Produto', backref='itens_estoque')

    tipo = db.Column(db.String(20))  # 'arma', 'municao', 'pce', 'nao_controlado'
    status = db.Column(db.String(30), default='disponivel')

    numero_serie = db.Column(db.String(100), unique=True, nullable=True)
    numero_embalagem = db.Column(db.String(100), nullable=True)
    lote = db.Column(db.String(100), nullable=True)
    quantidade_embalagem = db.Column(db.Integer, nullable=True)
    quantidade_disponivel = db.Column(db.Integer, nullable=True, default=0)

    nf_compra = db.Column(db.String(44), nullable=True)
    pedido_compra_id = db.Column(db.Integer, nullable=True)
    cliente_id = db.Column(db.Integer, nullable=True)

    data_recebimento = db.Column(db.DateTime, default=datetime.utcnow)
    data_venda = db.Column(db.DateTime, nullable=True)
    data_entrega = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        iden = self.numero_serie or self.numero_embalagem or '-'
        return f"<ItemEstoque {self.tipo}:{iden} - {self.status}>"
