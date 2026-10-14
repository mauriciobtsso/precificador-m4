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

# =========================
# Links Úteis
# =========================
class LinkUtil(db.Model):
    """Link editorial controlado pela administração e exibido na loja pública."""

    __tablename__ = "loja_links_uteis"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    resumo = db.Column(db.String(500), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    ordem = db.Column(db.Integer, nullable=False, default=0, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LinkUtil {self.titulo}>"


class PerguntaFrequente(db.Model):
    """Pergunta e resposta editáveis exibidas na FAQ pública da loja."""

    __tablename__ = "loja_perguntas_frequentes"
    __table_args__ = (
        db.Index("ix_loja_faq_publicada_ordem", "publicada", "ordem"),
    )

    id = db.Column(db.Integer, primary_key=True)
    pergunta = db.Column(db.String(300), nullable=False)
    resposta = db.Column(db.Text, nullable=False)
    link_texto = db.Column(db.String(200), nullable=True)
    link_url = db.Column(db.String(1000), nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    publicada = db.Column(db.Boolean, nullable=False, default=True)
    criada_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizada_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self):
        return f"<PerguntaFrequente {self.id}: {self.pergunta[:40]}>"


class TaxaLojaLink(db.Model):
    """Taxa de parcelamento usada exclusivamente pela vitrine da loja."""

    __tablename__ = "taxas_loja_link"
    __table_args__ = (
        db.UniqueConstraint(
            "numero_parcelas",
            name="uq_taxas_loja_link_numero_parcelas",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    numero_parcelas = db.Column(db.Integer, nullable=False)
    juros = db.Column(db.Float, nullable=False, default=0.0, server_default="0")

    def __repr__(self):
        return f"<TaxaLojaLink {self.numero_parcelas}x: {self.juros}%>"
