from app import db
from datetime import datetime
from app.utils.datetime import now_local  # ✔️ Padronização do horário

class CategoriaProduto(db.Model):
    __tablename__ = "categoria_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    pai_id = db.Column(db.Integer, db.ForeignKey("categoria_produto.id"), nullable=True)

    # ✔️ Ajustes conforme OPÇÃO B (somente troca utcnow → now_local)
    criado_em = db.Column(db.DateTime, default=now_local)
    atualizado_em = db.Column(db.DateTime, default=now_local, onupdate=now_local)

    # relação autorreferente
    pai = db.relationship("CategoriaProduto", remote_side=[id], backref="subcategorias")

    def __repr__(self):
        return f"<CategoriaProduto {self.nome}>"

    @property
    def caminho_completo(self):
        """Exibe o caminho hierárquico: Armas de Fogo > Rifles"""
        nomes = [self.nome]
        atual = self.pai
        while atual:
            nomes.append(atual.nome)
            atual = atual.pai
        return " > ".join(reversed(nomes))
