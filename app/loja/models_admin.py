from datetime import datetime
from app.extensions import db

# =========================
# Gerenciamento de Banners
# =========================
class Banner(db.Model):
    __tablename__ = "loja_banners"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    imagem_url = db.Column(db.String(512), nullable=False)  # Caminho no R2 ou local
    link_destino = db.Column(db.String(512), nullable=True) # Para onde o clique leva
    ordem = db.Column(db.Integer, default=0)                # Ordem de exibição no carrossel
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Banner {self.titulo}>"

# =========================
# Páginas Institucionais
# =========================
class PaginaInstitucional(db.Model):
    __tablename__ = "loja_paginas"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False) # ex: 'politica-privacidade'
    conteudo = db.Column(db.Text, nullable=False)                # Conteúdo em HTML/Rich Text
    visivel_rodape = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Pagina {self.titulo}>"