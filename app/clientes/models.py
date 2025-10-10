from app.extensions import db
from datetime import datetime

# =========================
# Cliente
# =========================
class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150))
    apelido = db.Column(db.String(100))
    razao_social = db.Column(db.String(150))

    # Dados pessoais
    sexo = db.Column(db.String(10))
    data_nascimento = db.Column(db.Date)
    profissao = db.Column(db.String(100))
    estado_civil = db.Column(db.String(50))
    escolaridade = db.Column(db.String(100))
    naturalidade = db.Column(db.String(100))
    nacionalidade = db.Column(db.String(100))
    nome_pai = db.Column(db.String(150))
    nome_mae = db.Column(db.String(150))
    matricula = db.Column(db.String(100))

    # Documentos principais (dados diretos do cliente)
    documento = db.Column(db.String(30), unique=True)   # CPF
    rg = db.Column(db.String(30))
    rg_emissor = db.Column(db.String(100))
    cnh = db.Column(db.String(30))

    # Registros (CR, SIGMA, SINARM)
    cr = db.Column(db.String(30))
    cr_emissor = db.Column(db.String(100))
    data_validade_cr = db.Column(db.Date)  # Para alertas de vencimento
    sigma = db.Column(db.String(50))
    sinarm = db.Column(db.String(50))
    inscricao_estadual = db.Column(db.String(50))
    inscricao_municipal = db.Column(db.String(50))

    # Flags
    cac = db.Column(db.Boolean, default=False)
    filiado = db.Column(db.Boolean, default=False)
    policial = db.Column(db.Boolean, default=False)
    bombeiro = db.Column(db.Boolean, default=False)
    militar = db.Column(db.Boolean, default=False)
    iat = db.Column(db.Boolean, default=False)
    psicologo = db.Column(db.Boolean, default=False)
    atirador_n1 = db.Column(db.Boolean, default=False)
    atirador_n2 = db.Column(db.Boolean, default=False)
    atirador_n3 = db.Column(db.Boolean, default=False)

    # Controle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    documentos = db.relationship("Documento", back_populates="cliente", cascade="all, delete-orphan")
    armas = db.relationship("Arma", back_populates="cliente", cascade="all, delete-orphan")
    comunicacoes = db.relationship("Comunicacao", back_populates="cliente", cascade="all, delete-orphan")
    processos = db.relationship("Processo", back_populates="cliente", cascade="all, delete-orphan")
    vendas = db.relationship("Venda", back_populates="cliente", cascade="all, delete-orphan")

    enderecos = db.relationship(
        "EnderecoCliente",
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="select"
    )
    contatos = db.relationship(
        "ContatoCliente",
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return f"<Cliente {self.id} - {self.nome}>"


# =========================
# Endereço
# =========================
class EnderecoCliente(db.Model):
    __tablename__ = "clientes_enderecos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)

    cep = db.Column(db.String(20))
    logradouro = db.Column(db.String(255))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    tipo = db.Column(db.String(50), default="residencial")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="enderecos")

    def __repr__(self):
        return f"<EnderecoCliente {self.tipo} - {self.logradouro}, {self.numero} - {self.cidade}/{self.estado}>"


# =========================
# Contato
# =========================
class ContatoCliente(db.Model):
    __tablename__ = "clientes_contatos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)

    tipo = db.Column(db.String(50))  # telefone, celular, email
    valor = db.Column(db.String(150))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="contatos")

    def __repr__(self):
        return f"<ContatoCliente {self.tipo}: {self.valor}>"


# =========================
# Documento
# =========================
from datetime import datetime
from app import db


class Documento(db.Model):
    __tablename__ = "documentos"

    id = db.Column(db.Integer, primary_key=True)

    # FK para o cliente
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Tipo genérico (mantido por compatibilidade antiga)
    tipo = db.Column(db.String(50), nullable=False)  # RG, CNH, CR, CRAF, NF etc.

    # === NOVOS CAMPOS (para OCR, controle e padronização) ===
    categoria = db.Column(db.String(50), nullable=True, index=True)  # ex: CR, CRAF, RG...
    emissor = db.Column(db.String(50), nullable=True)                # ex: SINARM, SIGMA, SSP...
    numero_documento = db.Column(db.String(100), nullable=True, index=True)
    data_emissao = db.Column(db.Date, nullable=True)
    data_validade = db.Column(db.Date, nullable=True)
    validade_indeterminada = db.Column(db.Boolean, default=False, nullable=False)

    # === ARQUIVO E METADADOS ===
    nome_original = db.Column(db.Text)                # Nome original do arquivo enviado
    caminho_arquivo = db.Column(db.Text, nullable=False)  # Caminho interno no R2
    mime_type = db.Column(db.String(100))
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)

    observacoes = db.Column(db.Text, nullable=True)

    # === AUDITORIA ===
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # === RELACIONAMENTO ===
    cliente = db.relationship(
        "Cliente",
        back_populates="documentos",
        lazy="joined",
    )

    # === MÉTODOS AUXILIARES ===
    def __repr__(self):
        return f"<Documento id={self.id} tipo={self.tipo} cliente={self.cliente_id}>"

    @property
    def arquivo_enviado(self) -> bool:
        """Retorna True se o documento tiver um arquivo associado."""
        return bool(self.caminho_arquivo)

    @property
    def esta_vencido(self) -> bool:
        """Indica se o documento tem validade e já venceu."""
        if self.data_validade and not self.validade_indeterminada:
            return self.data_validade < datetime.utcnow().date()
        return False

    @property
    def dias_para_vencer(self):
        """Retorna os dias restantes para o vencimento."""
        if self.data_validade and not self.validade_indeterminada:
            delta = (self.data_validade - datetime.utcnow().date()).days
            return delta
        return None


# =========================
# Arma
# =========================
class Arma(db.Model):
    __tablename__ = "armas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)


    tipo = db.Column(db.String(50))                  # ex: "pistola"
    funcionamento = db.Column(db.String(50))         # ex: "semi_automatica"
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    calibre = db.Column(db.String(50))
    numero_serie = db.Column(db.String(100), unique=True)
    emissor_craf = db.Column(db.String(50))          # ex: "sigma"
    numero_sigma = db.Column(db.String(50))          # Nº Sigma / Registro
    categoria_adquirente = db.Column(db.String(60))
    validade_indeterminada = db.Column(db.Boolean, default=False)
    data_validade_craf = db.Column(db.Date)
    caminho_craf = db.Column(db.Text)
    data_aquisicao = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cliente = db.relationship("Cliente", back_populates="armas")

    def __repr__(self):
        return f"<Arma {self.modelo or ''} - {self.numero_serie}>"


# =========================
# Comunicação
# =========================
class Comunicacao(db.Model):
    __tablename__ = "comunicacoes"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # whatsapp, email
    assunto = db.Column(db.String(150))
    mensagem = db.Column(db.Text, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="comunicacoes")

    def __repr__(self):
        return f"<Comunicacao {self.tipo} - Cliente {self.cliente_id}>"


# =========================
# Processo
# =========================
class Processo(db.Model):
    __tablename__ = "processos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    tipo = db.Column(db.String(100), nullable=False)      # Ex: Aquisição de arma
    status = db.Column(db.String(50), default="em_andamento")  # em_andamento, concluido, cancelado
    descricao = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="processos")

    def __repr__(self):
        return f"<Processo {self.tipo} - {self.status}>"
