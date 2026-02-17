from app import db
from datetime import datetime
from app.utils.datetime import now_local
import re
from sqlalchemy import event

class CategoriaProduto(db.Model):
    __tablename__ = "categoria_produto"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(150), unique=True, index=True) # Para URLs amigáveis /loja/facas
    descricao = db.Column(db.String(255))
    icone_loja = db.Column(db.String(100), nullable=True) # Nome do ícone Bootstrap (ex: bi-backpack)
    ordem_exibicao = db.Column(db.Integer, default=0)
    
    pai_id = db.Column(db.Integer, db.ForeignKey("categoria_produto.id"), nullable=True)

    criado_em = db.Column(db.DateTime(timezone=True), default=now_local)
    atualizado_em = db.Column(db.DateTime(timezone=True), default=now_local, onupdate=now_local)

    pai = db.relationship("CategoriaProduto", remote_side=[id], backref="subcategorias")

    def __repr__(self):
        return f"<CategoriaProduto {self.nome}>"

    @property
    def caminho_completo(self):
        nomes = [self.nome]
        atual = self.pai
        while atual:
            nomes.append(atual.nome)
            atual = atual.pai
        return " > ".join(reversed(nomes))

# Automação de Slugs para Categorias
def gera_slug_categoria(target, value, oldvalue, initiator):
    if value and (not target.slug or value != oldvalue):
        texto = value.lower().strip()
        texto = re.sub(r'[^\w\s-]', '', texto)
        texto = re.sub(r'[\s_-]+', '-', texto)
        target.slug = texto

event.listen(CategoriaProduto.nome, 'set', gera_slug_categoria, retval=False)