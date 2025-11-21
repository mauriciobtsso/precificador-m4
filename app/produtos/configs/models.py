# ======================
# MODELOS — CONFIGURAÇÕES DE PRODUTOS
# ======================

from app import db
from datetime import datetime
from app.utils.datetime import now_local  # ✔️ Padronização de horário


# ------------------------------
# MARCA
# ------------------------------
class MarcaProduto(db.Model):
    __tablename__ = "marca_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=now_local)
    atualizado_em = db.Column(db.DateTime, default=now_local, onupdate=now_local)

def __repr__(self):
    try:
        nome = object.__getattribute__(self, "nome")
    except Exception:
        nome = None
    return f"<{self.__class__.__name__} {nome or 'sem_nome'}>"


# ------------------------------
# CALIBRE
# ------------------------------
class CalibreProduto(db.Model):
    __tablename__ = "calibre_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=now_local)
    atualizado_em = db.Column(db.DateTime, default=now_local, onupdate=now_local)

def __repr__(self):
    try:
        nome = object.__getattribute__(self, "nome")
    except Exception:
        nome = None
    return f"<{self.__class__.__name__} {nome or 'sem_nome'}>"


# ------------------------------
# TIPO
# ------------------------------
class TipoProduto(db.Model):
    __tablename__ = "tipo_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=now_local)
    atualizado_em = db.Column(db.DateTime, default=now_local, onupdate=now_local)

def __repr__(self):
    try:
        nome = object.__getattribute__(self, "nome")
    except Exception:
        nome = None
    return f"<{self.__class__.__name__} {nome or 'sem_nome'}>"


# ------------------------------
# FUNCIONAMENTO
# ------------------------------
class FuncionamentoProduto(db.Model):
    __tablename__ = "funcionamento_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=now_local)
    atualizado_em = db.Column(db.DateTime, default=now_local, onupdate=now_local)

def __repr__(self):
    try:
        nome = object.__getattribute__(self, "nome")
    except Exception:
        nome = None
    return f"<{self.__class__.__name__} {nome or 'sem_nome'}>"
