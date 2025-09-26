from app import db
from datetime import datetime

class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    apelido = db.Column(db.String(100))
    razao_social = db.Column(db.String(150))
    sexo = db.Column(db.String(10))
    data_nascimento = db.Column(db.Date)
    profissao = db.Column(db.String(100))
    estado_civil = db.Column(db.String(50))
    escolaridade = db.Column(db.String(100))
    naturalidade = db.Column(db.String(100))
    nome_pai = db.Column(db.String(150))
    nome_mae = db.Column(db.String(150))

    # Documentos
    documento = db.Column(db.String(30), unique=True)
    rg = db.Column(db.String(30))
    rg_emissor = db.Column(db.String(100))
    cnh = db.Column(db.String(30))

    # Contatos
    email = db.Column(db.String(150))
    telefone = db.Column(db.String(30))
    celular = db.Column(db.String(30))

    # Endereço
    endereco = db.Column(db.String(255))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    cep = db.Column(db.String(20))

    # Registros
    cr = db.Column(db.String(30))
    cr_emissor = db.Column(db.String(100))
    sigma = db.Column(db.String(50))
    sinarm = db.Column(db.String(50))

    # Categorias / Flags
    cac = db.Column(db.Boolean, default=False)
    filiado = db.Column(db.Boolean, default=False)
    policial = db.Column(db.Boolean, default=False)
    bombeiro = db.Column(db.Boolean, default=False)
    militar = db.Column(db.Boolean, default=False)
    iat = db.Column(db.Boolean, default=False)
    psicologo = db.Column(db.Boolean, default=False)

    # Controle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Cliente {self.nome}>"
