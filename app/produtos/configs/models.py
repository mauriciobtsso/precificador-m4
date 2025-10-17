# ======================
# MODELOS — CONFIGURAÇÕES DE PRODUTOS
# ======================

from app import db
from datetime import datetime


# ------------------------------
# MARCA
# ------------------------------
class MarcaProduto(db.Model):
    __tablename__ = "marca_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MarcaProduto {self.nome}>"


# ------------------------------
# CALIBRE
# ------------------------------
class CalibreProduto(db.Model):
    __tablename__ = "calibre_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CalibreProduto {self.nome}>"


# ------------------------------
# TIPO
# ------------------------------
class TipoProduto(db.Model):
    __tablename__ = "tipo_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TipoProduto {self.nome}>"


# ------------------------------
# FUNCIONAMENTO
# ------------------------------
class FuncionamentoProduto(db.Model):
    __tablename__ = "funcionamento_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FuncionamentoProduto {self.nome}>"
