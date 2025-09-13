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
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)


# =========================
# Produto
# =========================
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False)
    nome = db.Column(db.String(128), nullable=False)

    # Custos
    preco_fornecedor = db.Column(db.Float, default=0.0)
    desconto_fornecedor = db.Column(db.Float, default=0.0)
    custo_total = db.Column(db.Float, default=0.0)

    # Objetivos
    margem = db.Column(db.Float, default=0.0)
    lucro_alvo = db.Column(db.Float, nullable=True)
    preco_final = db.Column(db.Float, nullable=True)

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

        Regras adotadas:
        - IPI **não** entra no custo total (apenas serve como referência e fica fora do custo).
        - A base do DIFAL **exclui** o IPI (ou seja, DIFAL incide sobre a base sem IPI).
        - DIFAL entra no custo total.
        - Preço final pode ser definido manualmente; senão é sugerido por lucro alvo ou margem.
        - Imposto sobre a venda (Simples) impacta no lucro líquido.
        """
        # 1) Base de compra com desconto do fornecedor
        base = (self.preco_fornecedor or 0.0) * (1 - (self.desconto_fornecedor or 0.0) / 100.0)

        # 2) IPI calculado (apenas para referência)
        if (self.ipi_tipo or "%") == "%":
            self.valor_ipi = base * (self.ipi or 0.0) / 100.0
        else:
            self.valor_ipi = (self.ipi or 0.0)

        # 3) Base do DIFAL **sem IPI**
        base_difal = max(base - (self.valor_ipi or 0.0), 0.0)

        # 4) DIFAL entra no custo
        self.valor_difal = base_difal * (self.difal or 0.0) / 100.0

        # 5) Custo total (base + DIFAL; IPI não entra)
        self.custo_total = base + self.valor_difal

        # 6) Definição do preço sugerido
        preco_sugerido = self.custo_total

        # Se houver lucro alvo, prioriza
        if (self.lucro_alvo is not None) and (self.lucro_alvo > 0):
            # preço final antes do imposto: custo + lucro
            # depois ajusta para o imposto sobre a venda (Simples)
            imposto = (self.imposto_venda or 0.0) / 100.0
            if 1.0 - imposto <= 0:
                preco_sugerido = self.custo_total + (self.lucro_alvo or 0.0)
            else:
                preco_sugerido = (self.custo_total + (self.lucro_alvo or 0.0)) / (1.0 - imposto)

        # Senão, usa margem %
        elif (self.margem or 0.0) > 0:
            imposto = (self.imposto_venda or 0.0) / 100.0
            venda_sem_imposto = self.custo_total * (1.0 + (self.margem or 0.0) / 100.0)
            if 1.0 - imposto <= 0:
                preco_sugerido = venda_sem_imposto
            else:
                preco_sugerido = venda_sem_imposto / (1.0 - imposto)

        # 7) Preço final (se não houver manual, usa sugerido)
        self.preco_final = self.preco_final or preco_sugerido

        # 8) Preço à vista = preço final (neste sistema)
        self.preco_a_vista = self.preco_final or 0.0

        # 9) Imposto sobre a venda (Simples)
        imposto_sobre_venda = (self.preco_final or 0.0) * (self.imposto_venda or 0.0) / 100.0

        # 10) Lucro líquido real
        self.lucro_liquido_real = (self.preco_final or 0.0) - self.custo_total - imposto_sobre_venda


# =========================
# Taxa
# =========================
class Taxa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_parcelas = db.Column(db.Integer, nullable=False)  # 1,2,3,... / 0 e negativos são inválidos
    juros = db.Column(db.Float, default=0.0)                 # armazenado em %


# =========================
# Configuração
# =========================
class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(64), unique=True, nullable=False)
    valor = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Config {self.chave}={self.valor}>"

    @classmethod
    def seed_defaults(cls):
        """
        Cria chaves padrão se não existirem.
        - incluir_pix: "true" | "false"
        - debito_percent: "1.09" (padrão 1,09%)
        - mensagem_whats_prefixo: texto opcional (ex.: "Oferta válida para hoje")
        """
        defaults = {
            "incluir_pix": "true",
            "debito_percent": "1.09",
            "mensagem_whats_prefixo": "",
        }
        for k, v in defaults.items():
            if not cls.query.filter_by(chave=k).first():
                db.session.add(cls(chave=k, valor=v))
