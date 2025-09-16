from app import db, login_manager
from flask_login import UserMixin

# =========================
# Login loader
# =========================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# Usuário
# =========================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)


# =========================
# Produto
# =========================
class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False)
    nome = db.Column(db.String(128), nullable=False)

    # Custos
    preco_fornecedor = db.Column(db.Float, default=0.0)
    desconto_fornecedor = db.Column(db.Float, default=0.0)
    custo_total = db.Column(db.Float, default=0.0)

    # Objetivos
    margem = db.Column(db.Float, default=0.0)          # margem em %
    lucro_alvo = db.Column(db.Float, nullable=True)    # lucro em R$
    preco_final = db.Column(db.Float, nullable=True)   # preço calculado

    # Tributos
    ipi = db.Column(db.Float, default=0.0)
    ipi_tipo = db.Column(db.String(2), default="%")  # "%" ou "R$"
    difal = db.Column(db.Float, default=0.0)
    imposto_venda = db.Column(db.Float, default=0.0)  # Simples Nacional (%)

    # Valores calculados
    valor_ipi = db.Column(db.Float, default=0.0)
    valor_difal = db.Column(db.Float, default=0.0)
    preco_a_vista = db.Column(db.Float, default=0.0)
    lucro_liquido_real = db.Column(db.Float, default=0.0)

    def calcular_precos(self):
        """
        Recalcula todos os valores do produto.
        """
        # 1) Base de compra com desconto
        base = (self.preco_fornecedor or 0.0) * (1 - (self.desconto_fornecedor or 0.0) / 100.0)

        # 2) IPI (referência)
        if (self.ipi_tipo or "%") == "%":
            self.valor_ipi = base * (self.ipi or 0.0) / 100.0
        else:
            self.valor_ipi = (self.ipi or 0.0)

        # 3) Base do DIFAL sem IPI
        base_difal = max(base - (self.valor_ipi or 0.0), 0.0)

        # 4) DIFAL entra no custo
        self.valor_difal = base_difal * (self.difal or 0.0) / 100.0

        # 5) Custo total
        self.custo_total = base + self.valor_difal

        # 6) Definição do preço sugerido
        preco_sugerido = self.custo_total
        imposto = (self.imposto_venda or 0.0) / 100.0

        if (self.lucro_alvo is not None) and (self.lucro_alvo > 0):
            if 1.0 - imposto <= 0:
                preco_sugerido = self.custo_total + (self.lucro_alvo or 0.0)
            else:
                preco_sugerido = (self.custo_total + (self.lucro_alvo or 0.0)) / (1.0 - imposto)
        elif (self.margem or 0.0) > 0:
            den_margem = 1.0 - (self.margem or 0.0) / 100.0
            if den_margem <= 0:
                venda_sem_imposto = self.custo_total
            else:
                venda_sem_imposto = self.custo_total / den_margem
            preco_sugerido = venda_sem_imposto

        self.preco_final = preco_sugerido
        self.preco_a_vista = self.preco_final or 0.0

        # Imposto sobre a venda
        imposto_sobre_venda = (self.preco_final or 0.0) * (self.imposto_venda or 0.0) / 100.0

        # Lucro líquido real
        self.lucro_liquido_real = (self.preco_final or 0.0) - self.custo_total - imposto_sobre_venda


# =========================
# Taxa
# =========================
class Taxa(db.Model):
    __tablename__ = "taxas"

    id = db.Column(db.Integer, primary_key=True)
    numero_parcelas = db.Column(db.Integer, nullable=False)
    juros = db.Column(db.Float, default=0.0)  # em %


# =========================
# Configuração
# =========================
class Configuracao(db.Model):
    __tablename__ = "configuracoes"

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(64), unique=True, nullable=False)
    valor = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Config {self.chave}={self.valor}>"

    @classmethod
    def seed_defaults(cls):
        defaults = {
            "incluir_pix": "true",
            "debito_percent": "1.09",
            "mensagem_whats_prefixo": "",
        }
        for k, v in defaults.items():
            if not cls.query.filter_by(chave=k).first():
                db.session.add(cls(chave=k, valor=v))


# =========================
# Cliente
# =========================
class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    razao_social = db.Column(db.String(150))
    sexo = db.Column(db.String(10))
    profissao = db.Column(db.String(100))

    documento = db.Column(db.String(30), unique=True, nullable=True)  # CPF/CNPJ
    rg = db.Column(db.String(30))
    rg_emissor = db.Column(db.String(100))

    email = db.Column(db.String(150))
    telefone = db.Column(db.String(30))
    celular = db.Column(db.String(30))

    endereco = db.Column(db.String(255))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    cep = db.Column(db.String(20))

    cr = db.Column(db.String(30))
    cr_emissor = db.Column(db.String(100))
    sigma = db.Column(db.String(50))
    sinarm = db.Column(db.String(50))

    cac = db.Column(db.Boolean, default=False)
    filiado = db.Column(db.Boolean, default=False)
    policial = db.Column(db.Boolean, default=False)
    bombeiro = db.Column(db.Boolean, default=False)
    militar = db.Column(db.Boolean, default=False)
    iat = db.Column(db.Boolean, default=False)
    psicologo = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()
    )

    # Relacionamentos
    vendas = db.relationship("Venda", backref="cliente", lazy=True)


# =========================
# Venda
# =========================
class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)

    vendedor = db.Column(db.String(100))
    status = db.Column(db.String(50))
    status_financeiro = db.Column(db.String(50))
    data_abertura = db.Column(db.DateTime)
    data_fechamento = db.Column(db.DateTime)
    data_quitacao = db.Column(db.DateTime)
    valor_total = db.Column(db.Float, nullable=False)

    nf_numero = db.Column(db.String(50))
    nf_valor = db.Column(db.Float)
    teve_devolucao = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()
    )

    # Relacionamento
    itens = db.relationship("ItemVenda", backref="venda", lazy=True)


# =========================
# Item de Venda
# =========================
class ItemVenda(db.Model):
    __tablename__ = "itens_venda"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)

    produto_nome = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(100))
    quantidade = db.Column(db.Integer, default=1)
    valor_unitario = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
