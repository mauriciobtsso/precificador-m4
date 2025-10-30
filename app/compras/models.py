# ============================================================
# MÓDULO: COMPRAS — Modelos de NF e Itens
# ============================================================

from app import db
from datetime import datetime
from decimal import Decimal
import uuid


# ============================================================
# MODELO: COMPRA NF
# ============================================================
class CompraNF(db.Model):
    __tablename__ = "compra_nf"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50))
    # ⚙️ permite vazio (None) e evita erro de duplicidade
    chave = db.Column(db.String(200), unique=True, nullable=True, index=True)
    fornecedor = db.Column(db.String(120))
    data_emissao = db.Column(db.DateTime)
    valor_total = db.Column(db.Numeric(12, 2))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # relacionamento
    itens = db.relationship("CompraItem", back_populates="nf", cascade="all, delete-orphan")

    # ============================================================
    # Métodos utilitários
    # ============================================================
    def calcular_total(self):
        """Soma o total de todos os itens e atualiza o campo valor_total."""
        self.valor_total = sum((i.valor_total or 0) for i in self.itens or [])

    def gerar_chave_unica(self):
        """Gera uma chave UUID se nenhuma chave existir."""
        if not self.chave:
            self.chave = str(uuid.uuid4())

    def __repr__(self):
        return f"<CompraNF id={self.id} numero={self.numero} fornecedor='{self.fornecedor}'>"


# ============================================================
# MODELO: COMPRA ITEM
# ============================================================
class CompraItem(db.Model):
    __tablename__ = "compra_item"

    id = db.Column(db.Integer, primary_key=True)
    nf_id = db.Column(db.Integer, db.ForeignKey("compra_nf.id", ondelete="CASCADE"))
    descricao = db.Column(db.String(250))
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    calibre = db.Column(db.String(50))
    lote = db.Column(db.String(100))
    quantidade = db.Column(db.Numeric(10, 2))
    valor_unitario = db.Column(db.Numeric(10, 2))
    valor_total = db.Column(db.Numeric(12, 2))

    nf = db.relationship("CompraNF", back_populates="itens")

    # ============================================================
    # Métodos utilitários
    # ============================================================
    def calcular_total(self):
        """Calcula o total (quantidade × valor unitário)."""
        try:
            q = Decimal(self.quantidade or 0)
            v = Decimal(self.valor_unitario or 0)
            self.valor_total = q * v
        except Exception:
            self.valor_total = Decimal(0)

    def __repr__(self):
        return f"<CompraItem id={self.id} desc='{self.descricao}' q={self.quantidade}>"