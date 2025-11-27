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


# =========================
# Pedido de Compra
# =========================
class PedidoCompra(db.Model):
    __tablename__ = "pedido_compra"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    data_pedido = db.Column(db.Date, nullable=False)
    cond_pagto = db.Column(db.String(100))

    # === STATUS DO FLUXO (Adicionado) ===
    # Opções: Aguardando, Confirmado, Aguardando NF, Em Transito, Recebido, Cancelado
    status = db.Column(db.String(30), default="Aguardando", index=True)

    modo_desconto = db.Column(db.String(20), default="por_tipo")
    percentual_armas = db.Column(db.Float, default=0.0)
    percentual_municoes = db.Column(db.Float, default=0.0)
    percentual_unico = db.Column(db.Float, default=0.0)

    fornecedor_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)

    # Relacionamento com Cliente atuando como fornecedor
    fornecedor = db.relationship("Cliente", backref="pedidos_compra", foreign_keys=[fornecedor_id])

    itens = db.relationship("ItemPedido", backref="pedido", cascade="all, delete-orphan")
    
    # O relacionamento com notas fiscais (nfs) será criado pelo backref em CompraNF


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


# =========================
# Modelos de Documentos (Contratos/Recibos)
# =========================
class ModeloDocumento(db.Model):
    __tablename__ = "modelos_documento"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)  # Ex: Contrato de Arma
    chave = db.Column(db.String(50), unique=True, nullable=False)  # Ex: contrato_arma
    conteudo = db.Column(db.Text, nullable=False)  # HTML com placeholders Jinja2
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ModeloDocumento {self.titulo}>"