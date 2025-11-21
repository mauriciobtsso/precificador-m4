# ============================================================
# app/importacoes/models.py
# ============================================================

from app import db
from app.utils.datetime import now_local

class ImportacaoLog(db.Model):
    __tablename__ = "importacoes_log"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False, default="produtos")
    usuario = db.Column(db.String(100), nullable=True)
    data_hora = db.Column(db.DateTime(timezone=True), default=now_local)
    novos = db.Column(db.Integer, nullable=False, default=0)
    atualizados = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "usuario": self.usuario,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
            "novos": self.novos,
            "atualizados": self.atualizados,
            "total": self.total,
        }

    def __repr__(self):
        return f"<ImportacaoLog {self.id} - {self.tipo} ({self.usuario})>"
