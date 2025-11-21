from flask import Flask
from jinja2.runtime import Undefined
from sqlalchemy import inspect
from config import Config
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pytz  # ✅ para fuso horário

# Importa extensões centralizadas
from app.extensions import db, login_manager, migrate
from app.produtos.configs import models as configs_models

load_dotenv()

# =========================================================
# FUSO HORÁRIO PADRÃO — agora movido para app/utils/datetime.py
# =========================================================
from app.utils.datetime import now_local


# =========================================================
# LOGGING
# =========================================================
def configure_logging(app):
    """Configura logs em arquivo (rotativo) e no console."""
    if getattr(app, "_logging_configured", False):
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "precificador.log"),
        maxBytes=10 * 1024 * 1024,
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


# =========================================================
# FUSO HORÁRIO PADRÃO — AMÉRICA/FORTALEZA (UTC-3)
# =========================================================
import pytz
from datetime import datetime, timedelta, timezone

# Definição de timezone local (sem horário de verão)
TZ_FORTALEZA = pytz.timezone("America/Fortaleza")

def now_local():
    """Retorna o horário local padronizado em UTC-3 (Teresina), ignorando horário de verão."""
    # datetime.now(tz=TZ_FORTALEZA) respeita o offset real da região
    dt = datetime.now(tz=TZ_FORTALEZA)
    # Remove possíveis ajustes indevidos do Windows
    return dt.replace(tzinfo=timezone(timedelta(hours=-3)))


# =========================================================
# APP FACTORY
# =========================================================
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 🔧 Pasta de uploads
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        from app.config import UPLOAD_FOLDER
        upload_folder = UPLOAD_FOLDER
        app.config["UPLOAD_FOLDER"] = upload_folder

    os.makedirs(upload_folder, exist_ok=True)
    app.logger.info(f"[UPLOAD] Pasta configurada em: {upload_folder}")

    # 🚨 Proteção: evita testes em banco de produção
    if app.config.get("TESTING") and "neon.tech" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        raise RuntimeError("⚠️ Testes NÃO podem rodar em banco de produção (Neon)!")

    # Logging
    configure_logging(app)

    # Extensões
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    migrate.init_app(app, db)

    # =========================================================
    # REGISTRO DE BLUEPRINTS
    # =========================================================
    from app.main import main
    from app.admin import admin_bp
    from app.clientes.routes import clientes_bp
    from app.vendas import vendas_bp
    from app.produtos import produtos_bp
    from app.produtos.configs.routes import configs_bp
    from app.produtos.categorias.routes import categorias_bp
    from app.taxas.routes import taxas_bp
    from app.pedidos import pedidos_bp
    from app.estoque import estoque_bp
    from app.uploads import uploads_bp
    from app.alertas import alertas_bp
    from app.notificacoes import notificacoes_bp
    from app.compras import compras_nf_bp
    from app.importacoes import importacoes_bp

    app.register_blueprint(uploads_bp, url_prefix="/uploads")
    app.register_blueprint(main)
    app.register_blueprint(clientes_bp, url_prefix="/clientes")
    app.register_blueprint(produtos_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(configs_bp)
    app.register_blueprint(vendas_bp, url_prefix="/vendas")
    app.register_blueprint(categorias_bp)
    app.register_blueprint(taxas_bp)
    app.register_blueprint(pedidos_bp, url_prefix="/pedidos")
    app.register_blueprint(alertas_bp)
    app.register_blueprint(notificacoes_bp)
    app.register_blueprint(compras_nf_bp)
    app.register_blueprint(importacoes_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # =========================================================
    # AGENDADOR DE ALERTAS
    # =========================================================
    from app.alertas.tasks import iniciar_scheduler
    iniciar_scheduler(app)

    # =========================================================
    # FILTRO CUSTOMIZADO JINJA — currency
    # =========================================================
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
    # Filtro customizado: dt_local
    # -------------------------
    from datetime import timezone
    import pytz

    def format_datetime_local(dt, fmt="%d/%m/%Y %H:%M", tzname="America/Fortaleza"):
        """Converte datetime (UTC ou naive) para o fuso informado e formata."""
        if not dt:
            return ""
        try:
            tz = pytz.timezone(tzname)
            # Se vier sem tzinfo, consideramos UTC para manter consistência
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(tz).strftime(fmt)
        except Exception:
            # fallback: formata como vier
            try:
                return dt.strftime(fmt)
            except Exception:
                return str(dt)

    app.jinja_env.filters["dt_local"] = format_datetime_local


    # =========================================================
    # CONTEXTO GLOBAL DE DATA/HORA LOCAL
    # =========================================================
    @app.context_processor
    def inject_now():
        """Disponibiliza now_local() nos templates Jinja."""
        return {"now_local": now_local}

    # =========================================================
    # SEED INICIAL
    # =========================================================
    if not app.config.get("TESTING"):
        from app.models import User, Taxa, Configuracao
        from app.produtos.models import Produto

        with app.app_context():
            inspector = inspect(db.engine)
            tabelas = set(inspector.get_table_names())

            if {"users", "taxas", "produtos", "configuracoes"}.issubset(tabelas):
                if not User.query.filter_by(username="admin").first():
                    admin = User(username="admin")
                    admin.set_password("admin")
                    db.session.add(admin)

                if not Taxa.query.first():
                    taxas = [
                        Taxa(numero_parcelas=0, juros=1.09),
                        Taxa(numero_parcelas=1, juros=3.48),
                        Taxa(numero_parcelas=2, juros=5.1),
                        Taxa(numero_parcelas=3, juros=5.92),
                        Taxa(numero_parcelas=4, juros=6.79),
                        Taxa(numero_parcelas=5, juros=7.61),
                        Taxa(numero_parcelas=6, juros=8.43),
                        Taxa(numero_parcelas=7, juros=9.25),
                        Taxa(numero_parcelas=8, juros=10.07),
                        Taxa(numero_parcelas=9, juros=10.89),
                        Taxa(numero_parcelas=10, juros=11.71),
                        Taxa(numero_parcelas=11, juros=12.53),
                        Taxa(numero_parcelas=12, juros=13.35),
                    ]
                    db.session.add_all(taxas)

                Configuracao.seed_defaults()
                db.session.commit()

    return app
