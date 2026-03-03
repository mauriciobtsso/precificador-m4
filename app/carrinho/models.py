from app import db
from datetime import datetime
from app.utils.datetime import now_local

class Carrinho(db.Model):
    __tablename__ = 'carrinhos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Opcional se for visitante
    session_id = db.Column(db.String(100), index=True) # Identificador para usuários não logados
    criado_em = db.Column(db.DateTime, default=now_local)
    atualizado_em = db.Column(db.DateTime, onupdate=now_local)
    
    items = db.relationship('CarrinhoItem', backref='carrinho', cascade="all, delete-orphan")

    @property
    def total_avista(self):
        """
        Calcula o total do carrinho somando os subtotais de todos os itens.
        Retorna um valor numérico arredondado a 2 casas decimais.
        """
        total = sum(float(item.subtotal_avista or 0) for item in self.items)
        return round(total, 2)

    @property
    def requer_documentacao(self):
        """
        Verifica se algum item do carrinho requer documentação especial.
        Retorna True se pelo menos um produto requer documentação.
        """
        return any(item.produto.requer_documentacao for item in self.items)

class CarrinhoItem(db.Model):
    __tablename__ = 'carrinho_items'
    id = db.Column(db.Integer, primary_key=True)
    carrinho_id = db.Column(db.Integer, db.ForeignKey('carrinhos.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Integer, default=1)
    preco_unitario_no_momento = db.Column(db.Numeric(12, 2)) # Proteção contra mudança de preço

    produto = db.relationship('Produto')

    @property
    def subtotal_avista(self):
        """
        Calcula o subtotal do item multiplicando a quantidade pelo preço unitário.
        Garante que valores nulos sejam tratados como 0.
        """
        preco = float(self.preco_unitario_no_momento or 0)
        return round(preco * self.quantidade, 2)

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    
    # Rastreabilidade do Cliente
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    nome_cliente = db.Column(db.String(100), nullable=False)
    email_cliente = db.Column(db.String(100), nullable=False)
    documento = db.Column(db.String(20), nullable=False) # CPF/CNPJ
    telefone = db.Column(db.String(20))

    # Endereço de Entrega (Snapshot - não muda se o cliente mudar o cadastro depois)
    cep = db.Column(db.String(10), nullable=False)
    logradouro = db.Column(db.String(255), nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    bairro = db.Column(db.String(100), nullable=False)
    cidade = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(2), nullable=False)

    # Valores e Financeiro
    total_produtos = db.Column(db.Numeric(12, 2), nullable=False)
    total_frete = db.Column(db.Numeric(12, 2), default=0.00)
    total_pedido = db.Column(db.Numeric(12, 2), nullable=False)
    forma_pagamento = db.Column(db.String(20)) # 'pix' ou 'credit_card'
    parcelas = db.Column(db.Integer, default=1)
    
    # Integração Pagar.me
    pagarme_id = db.Column(db.String(100), index=True) # ID do Pedido no Pagar.me
    status = db.Column(db.String(30), default='pendente') # pendente, pago, cancelado, estornado
    
    # Logística e Datas
    criado_em = db.Column(db.DateTime, default=now_local)
    pago_em = db.Column(db.DateTime, nullable=True)  # Campo adicionado para rastreamento de pagamento
    items = db.relationship('PedidoItem', backref='pedido', cascade="all, delete-orphan")

class PedidoItem(db.Model):
    __tablename__ = 'pedido_items'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario_historico = db.Column(db.Numeric(12, 2), nullable=False) # Valor no dia da compra
    
    produto = db.relationship('Produto')
