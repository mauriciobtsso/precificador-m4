from app import db
from datetime import datetime
from app.produtos.models import Produto
from app.clientes.models import Cliente
from app.utils.datetime import now_local  # ✔️ Padronização de horário aplicada

class ItemEstoque(db.Model):
    __tablename__ = "estoque_itens"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)

    tipo_item = db.Column(db.String(20), nullable=False)  # arma, municao, pce, nao_controlado
    numero_serie = db.Column(db.String(100), nullable=True)
    lote = db.Column(db.String(50), nullable=True)
    numero_embalagem = db.Column(db.String(50), nullable=True)
    quantidade = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default="disponivel", nullable=False)

    # ✔️ Ajuste conforme OPÇÃO B (sem alterar tipo da coluna)
    data_entrada = db.Column(db.Date, default=lambda: now_local().date())

    observacoes = db.Column(db.Text, nullable=True)

    produto = db.relationship("Produto", backref="itens_estoque")
    fornecedor = db.relationship("Cliente", backref="itens_fornecidos")

    def __repr__(self):
        nome = self.produto.nome if self.produto else "Desconhecido"
        return f"<ItemEstoque {self.id} [{self.tipo_item}] {nome} - {self.status}>"
