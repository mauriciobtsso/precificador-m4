from flask import Flask
from jinja2.runtime import Undefined
from sqlalchemy import inspect
from config import Config
import os
import logging
from logging.handlers import RotatingFileHandler

# Importa extensões centralizadas
from app.extensions import db, login_manager, migrate


def configure_logging(app):
    """Configura logs em arquivo (rotativo) e no console (Render captura stdout)."""
    if getattr(app, "_logging_configured", False):
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "precificador.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    app.logger.setLevel(level)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False

    app._logging_configured = True
    app.logger.info("Logging configurado (nível=%s)", log_level_name)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 🚨 Proteção contra testes em banco de produção
    if app.config.get("TESTING") and "neon.tech" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        raise RuntimeError("⚠️ Testes NÃO podem rodar em banco de produção (Neon)!")

    # Configuração de logging
    configure_logging(app)

    # Inicializa extensões
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    migrate.init_app(app, db)

    # Registrar blueprints
    from app.main import main
    from app.clientes.routes import clientes_bp
    from app.vendas import vendas_bp
    from app.produtos import produtos_bp
    from app.taxas.routes import taxas_bp
    from app.pedidos import pedidos_bp   # 👈 novo módulo de pedidos
    from app.uploads import uploads_bp

    app.register_blueprint(uploads_bp)
    app.register_blueprint(main)
    app.register_blueprint(clientes_bp, url_prefix="/clientes")
    app.register_blueprint(vendas_bp, url_prefix="/vendas")
    app.register_blueprint(produtos_bp, url_prefix="/produtos")
    app.register_blueprint(taxas_bp)
    app.register_blueprint(pedidos_bp, url_prefix="/pedidos")  # 👈 registra pedidos

    # -------------------------
    # Filtro customizado: currency
    # -------------------------
    def format_currency(value):
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
    # Seed inicial (apenas se tabelas existirem e NÃO for ambiente de teste)
    # -------------------------
    if not app.config.get("TESTING"):
        from app.models import User, Taxa, Produto, Configuracao

        with app.app_context():
            inspector = inspect(db.engine)
            tabelas = set(inspector.get_table_names())

            if {"users", "taxas", "produtos", "configuracoes"}.issubset(tabelas):
                # Usuário admin
                if not User.query.filter_by(username="admin").first():
                    admin = User(username="admin")
                    admin.set_password("admin")
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
