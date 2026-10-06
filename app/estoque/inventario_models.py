"""Modelos de conferência física do inventário de munições."""
from app import db
from app.utils.datetime import now_local


class ConferenciaInventario(db.Model):
    __tablename__ = "estoque_conferencias_municao"

    id = db.Column(db.Integer, primary_key=True)
    data_conferencia = db.Column(db.Date, nullable=False, default=lambda: now_local().date(), index=True)
    status = db.Column(db.String(20), nullable=False, default="aberta", index=True)
    observacoes = db.Column(db.Text, nullable=True)
    loja_cnpj = db.Column(db.String(30), nullable=True)
    loja_nome = db.Column(db.String(180), nullable=True)
    loja_endereco = db.Column(db.Text, nullable=True)
    loja_cr = db.Column(db.String(50), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=now_local)
    finalizado_em = db.Column(db.DateTime, nullable=True)

    itens = db.relationship(
        "ConferenciaInventarioItem",
        back_populates="conferencia",
        cascade="all, delete-orphan",
        order_by="ConferenciaInventarioItem.id",
    )


class ConferenciaInventarioItem(db.Model):
    __tablename__ = "estoque_conferencia_municao_itens"
    __table_args__ = (
        db.UniqueConstraint("conferencia_id", "identificacao_embalagem", name="uq_conferencia_embalagem"),
    )

    id = db.Column(db.Integer, primary_key=True)
    conferencia_id = db.Column(
        db.Integer,
        db.ForeignKey("estoque_conferencias_municao.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True, index=True)
    codigo_municao = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    calibre = db.Column(db.String(80), nullable=True)
    lote = db.Column(db.String(80), nullable=True)
    identificacao_embalagem = db.Column(db.String(120), nullable=False)
    quantidade_embalagem = db.Column(db.Integer, nullable=False)
    quantidade_total = db.Column(db.Integer, nullable=False)
    lido_em = db.Column(db.DateTime, nullable=False, default=now_local)

    conferencia = db.relationship("ConferenciaInventario", back_populates="itens")
    produto = db.relationship("Produto")
