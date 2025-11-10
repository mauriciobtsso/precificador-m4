from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Importa extensões centralizadas
from app.extensions import db, login_manager


# =========================
# Login loader
# =========================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# Usuário
# =========================
class User(UserMixin, db.Model):  # <- herda UserMixin para Flask-Login
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    # mantém 512 para suportar hashes longos (pbkdf2/scrypt)
    password_hash = db.Column(db.String(512), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


# =========================
# Produto
# =========================
#class Produto(db.Model):
#    __tablename__ = "produtos"
#
#    id = db.Column(db.Integer, primary_key=True)
#    sku = db.Column(db.String(64), unique=True, nullable=False)
#    nome = db.Column(db.String(128), nullable=False)
#
#    # Custos
#    preco_fornecedor = db.Column(db.Float, default=0.0)
#    desconto_fornecedor = db.Column(db.Float, default=0.0)
#    custo_total = db.Column(db.Float, default=0.0)
#
#    # Objetivos
#    margem = db.Column(db.Float, default=0.0)          # margem em %
#    lucro_alvo = db.Column(db.Float, nullable=True)    # lucro em R$
#    preco_final = db.Column(db.Float, nullable=True)   # preço calculado
#
#    # Tributos
#    ipi = db.Column(db.Float, default=0.0)
#    ipi_tipo = db.Column(db.String(15), default="%_dentro")  # "%_dentro", "%", "R$"
#    difal = db.Column(db.Float, default=0.0)
#    imposto_venda = db.Column(db.Float, default=0.0)  # Simples Nacional (%)

#    # Valores calculados
#    frete = db.Column(db.Numeric(10, 2), default=0.00)
#    valor_ipi = db.Column(db.Float, default=0.0)
#    valor_difal = db.Column(db.Float, default=0.0)
#    preco_a_vista = db.Column(db.Float, default=0.0)
#    lucro_liquido_real = db.Column(db.Float, default=0.0)
#
#    def calcular_precos(self):
#        preco_compra = self.preco_fornecedor or 0.0
#        desconto = (self.desconto_fornecedor or 0.0) / 100.0
#        base = preco_compra * (1 - desconto)
#
#        # ===== IPI =====
#        if self.ipi_tipo == "%_dentro":
#            base_sem_ipi = base / (1 + (self.ipi or 0.0) / 100.0)
#            self.valor_ipi = base - base_sem_ipi
#        elif self.ipi_tipo == "%":
#            self.valor_ipi = base * (self.ipi or 0.0) / 100.0
#        else:  # "R$"
#            self.valor_ipi = self.ipi or 0.0
#
#        # ===== DIFAL =====
#        frete_valor = float(self.frete) if self.frete else 0.0
#        base_difal = max(base - (self.valor_ipi or 0.0) + frete_valor, 0.0)
#        self.valor_difal = base_difal * (self.difal or 0.0) / 100.0
#
#        # ===== Custo total =====
#        self.custo_total = base + self.valor_difal + frete_valor
#
#        preco_sugerido = self.custo_total
#        imposto = (self.imposto_venda or 0.0) / 100.0
#
#        # ===== Objetivos =====
#        if (self.preco_final is not None) and (self.preco_final > 0):
#            preco_sugerido = self.preco_final
#        elif (self.lucro_alvo is not None) and (self.lucro_alvo > 0):
#            if 1.0 - imposto <= 0:
#                preco_sugerido = self.custo_total + (self.lucro_alvo or 0.0)
#            else:
#                preco_sugerido = (self.custo_total + (self.lucro_alvo or 0.0)) / (1.0 - imposto)
#        elif (self.margem or 0.0) > 0:
#            den_margem = 1.0 - (self.margem or 0.0) / 100.0
#            if den_margem <= 0:
#                venda_sem_imposto = self.custo_total
#            else:
#                venda_sem_imposto = self.custo_total / den_margem
#            preco_sugerido = venda_sem_imposto
#
#        self.preco_final = preco_sugerido
#        self.preco_a_vista = self.preco_final or 0.0
#
#        imposto_sobre_venda = (self.preco_final or 0.0) * (self.imposto_venda or 0.0) / 100.0
#        self.lucro_liquido_real = (self.preco_final or 0.0) - self.custo_total - imposto_sobre_venda


# =========================
# Taxa
# =========================
class Taxa(db.Model):
    __tablename__ = "taxas"

    id = db.Column(db.Integer, primary_key=True)
    numero_parcelas = db.Column(db.Integer, nullable=False)
    juros = db.Column(db.Float, default=0.0)  # em %


# =========================
# Configuração
# =========================
class Configuracao(db.Model):
    __tablename__ = "configuracoes"

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(64), unique=True, nullable=False)
    valor = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Config {self.chave}={self.valor}>"

    @classmethod
    def seed_defaults(cls):
        defaults = {
            "incluir_pix": "true",
            "debito_percent": "1.09",
            "mensagem_whats_prefixo": "",
        }
        for k, v in defaults.items():
            if not cls.query.filter_by(chave=k).first():
                db.session.add(cls(chave=k, valor=v))

# >>> MOVIDO PARA app/vendas/models.py <<<
# =========================
# Venda
# =========================
# class Venda(db.Model):
#     __tablename__ = "vendas"
# 
#     id = db.Column(db.Integer, primary_key=True)
#     cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
# 
#     vendedor = db.Column(db.String(100))
#     status = db.Column(db.String(50))
#     status_financeiro = db.Column(db.String(50))
#     data_abertura = db.Column(db.DateTime)
#     data_fechamento = db.Column(db.DateTime)
#     data_quitacao = db.Column(db.DateTime)
#     valor_total = db.Column(db.Float, nullable=False)
# 
#     nf_numero = db.Column(db.String(50))
#     nf_valor = db.Column(db.Float)
#     teve_devolucao = db.Column(db.Boolean, default=False)
# 
#     created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
#     updated_at = db.Column(
#         db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()
#     )
# 
#     # Relacionamentos
#     itens = db.relationship("ItemVenda", backref="venda", lazy=True, cascade="all, delete-orphan")
#     cliente = db.relationship("Cliente", back_populates="vendas")
# 
#     def __repr__(self):
#         return f"<Venda {self.id} - Cliente {self.cliente_id}>"
# 
# 
# =========================
# Item de Venda
# =========================
# class ItemVenda(db.Model):
#     __tablename__ = "itens_venda"
# 
#     id = db.Column(db.Integer, primary_key=True)
#     venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)
# 
#     produto_nome = db.Column(db.String(200), nullable=False)
#     categoria = db.Column(db.String(100))
#     quantidade = db.Column(db.Integer, default=1)
#     valor_unitario = db.Column(db.Float, nullable=False)
#     valor_total = db.Column(db.Float, nullable=False)
# 
#     def __repr__(self):
#         return f"<ItemVenda {self.id} - {self.produto_nome}>"


# =========================
# Pedido de Compra
# =========================
class PedidoCompra(db.Model):
    __tablename__ = "pedido_compra"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    data_pedido = db.Column(db.Date, nullable=False)
    cond_pagto = db.Column(db.String(100))

    modo_desconto = db.Column(db.String(20), default="por_tipo")
    percentual_armas = db.Column(db.Float, default=0.0)
    percentual_municoes = db.Column(db.Float, default=0.0)
    percentual_unico = db.Column(db.Float, default=0.0)

    fornecedor_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)

    # Relacionamento com Cliente atuando como fornecedor
    fornecedor = db.relationship("Cliente", backref="pedidos_compra", foreign_keys=[fornecedor_id])

    itens = db.relationship("ItemPedido", backref="pedido", cascade="all, delete-orphan")


class ItemPedido(db.Model):
    __tablename__ = "item_pedido"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido_compra.id"), nullable=False)
    codigo = db.Column(db.String(50))
    descricao = db.Column(db.String(200))
    quantidade = db.Column(db.Integer)
    valor_unitario = db.Column(db.Float)


# =========================
# Notificação
# =========================
class Notificacao(db.Model):
    __tablename__ = "notificacao"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    tipo = db.Column(db.String(50), nullable=False)
    nivel = db.Column(db.String(20), nullable=True)
    mensagem = db.Column(db.Text, nullable=False)
    meio = db.Column(db.String(20), default="sistema")  # sistema, email, whatsapp
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="enviado")  # enviado, lido
    erro = db.Column(db.Text, nullable=True)

    # 🔹 Relação ORM com Cliente
    cliente = db.relationship("Cliente", backref="notificacoes", lazy=True)

    def to_dict(self):
        cliente_nome = None
        if self.cliente:
            # tenta obter o nome pelo campo disponível
            cliente_nome = getattr(self.cliente, "nome_razao", None) \
                or getattr(self.cliente, "razao_social", None) \
                or getattr(self.cliente, "nome", None) \
                or getattr(self.cliente, "nome_completo", None)

        return {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "cliente_nome": cliente_nome,
            "tipo": self.tipo,
            "nivel": self.nivel,
            "mensagem": self.mensagem,
            "meio": self.meio,
            "data_envio": self.data_envio.strftime("%d/%m/%Y %H:%M"),
            "status": self.status,
        }
