from flask import Flask
from jinja2.runtime import Undefined
from sqlalchemy import inspect
from config import Config

# Importa extensões centralizadas
from app.extensions import db, login_manager, migrate


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    migrate.init_app(app, db)

    # Registrar blueprints
    from app.main import main
    app.register_blueprint(main)

    from app.clientes.routes import clientes_bp
    app.register_blueprint(clientes_bp, url_prefix="/clientes")

    from app.vendas import vendas_bp
    app.register_blueprint(vendas_bp, url_prefix="/vendas")

    # -------------------------
    # Filtro customizado: currency
    # -------------------------
    def format_currency(value):
        """
        Converte números em formato monetário brasileiro.
        Ex: 1234.5 -> R$ 1.234,50
        """
        if value is None or isinstance(value, Undefined):
            return "R$ 0,00"
        try:
            v = float(value)
            formatted = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {formatted}"
        except Exception:
            return "R$ 0,00"

    app.jinja_env.filters["currency"] = format_currency

    # -------------------------
    # Seed inicial (apenas se tabelas existirem)
    # -------------------------
    from app.models import User, Taxa, Produto, Configuracao

    with app.app_context():
        inspector = inspect(db.engine)
        tabelas = set(inspector.get_table_names())

        if {"users", "taxas", "produtos", "configuracoes"}.issubset(tabelas):
            # Usuário admin (agora usando hash de senha)
            if not User.query.filter_by(username="admin").first():
                admin = User(username="admin")
                admin.set_password("admin")  # <- armazena hash seguro
                db.session.add(admin)

            # Taxas de parcelamento
            if not Taxa.query.first():
                taxas = [
                    Taxa(numero_parcelas=1, juros=0.0),
                    Taxa(numero_parcelas=2, juros=3.5),
                    Taxa(numero_parcelas=3, juros=6.2),
                    Taxa(numero_parcelas=4, juros=8.5),
                    Taxa(numero_parcelas=5, juros=10.2),
                    Taxa(numero_parcelas=6, juros=12.5),
                    Taxa(numero_parcelas=7, juros=14.3),
                    Taxa(numero_parcelas=8, juros=15.8),
                    Taxa(numero_parcelas=9, juros=17.1),
                    Taxa(numero_parcelas=10, juros=18.6),
                    Taxa(numero_parcelas=11, juros=19.9),
                    Taxa(numero_parcelas=12, juros=21.5),
                ]
                db.session.add_all(taxas)

            # Produtos de exemplo
            if not Produto.query.first():
                produtos = [
                    Produto(
                        sku="CBC8122",
                        nome="Rifle CBC 8122 Bolt Action 23\" OXPP",
                        preco_fornecedor=2500.00,
                        desconto_fornecedor=0,
                        margem=40,
                        ipi=10,
                        ipi_tipo="%",
                        difal=5,
                    ),
                    Produto(
                        sku="RT066INOX",
                        nome="Revólver Taurus RT 066 357Mag 4\" Inox Fosco",
                        preco_fornecedor=3500.00,
                        desconto_fornecedor=0,
                        margem=42,
                        ipi=12,
                        ipi_tipo="%",
                        difal=5,
                    ),
                    Produto(
                        sku="RT065OX",
                        nome="Revólver Taurus RT 065 357Mag 4\" Oxidado",
                        preco_fornecedor=3300.00,
                        desconto_fornecedor=0,
                        margem=40,
                        ipi=12,
                        ipi_tipo="%",
                        difal=5,
                    ),
                ]
                for p in produtos:
                    p.calcular_precos()
                    db.session.add(p)

            # Configurações padrão
            Configuracao.seed_defaults()

            db.session.commit()

    return app
