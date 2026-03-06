from flask import Flask, request
from jinja2.runtime import Undefined
from sqlalchemy import inspect
from config import Config
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from flask_ckeditor import CKEditor
from flask_compress import Compress

# Instancia extensões centralizadas
ckeditor = CKEditor()
compress = Compress()

# Importa extensões centralizadas
from app.extensions import db, login_manager, migrate
from app.loja.routes import cache
from app.produtos.configs import models as configs_models
from app.utils.datetime import now_local

load_dotenv()

# =========================================================
# LOGGING (Configuração de Campo)
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
        encoding="utf-8",
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
# APP FACTORY (Arsenal Central)
# =========================================================
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 🚀 ATIVAÇÃO DA COMPRESSÃO (Crítico para PageSpeed)
    compress.init_app(app)

    # 🔧 Pasta de uploads
    upload_folder = app.config.get("UPLOAD_FOLDER") or "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    # 🚨 Proteção: evita testes em banco de produção
    if app.config.get("TESTING") and "neon.tech" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        raise RuntimeError("⚠️ Testes NÃO podem rodar em banco de produção (Neon)!")

    # Logging
    configure_logging(app)

    # Inicializa Extensões
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    migrate.init_app(app, db)
    ckeditor.init_app(app)

    # 🚀 CONFIGURAÇÃO DE CACHE DE ATIVOS (SEO & PERFORMANCE)
    @app.after_request
    def add_header(response):
        # Cache de 1 ano para ativos estáticos (Imagens, Fontes, CSS, JS)
        # Resolve o problema de "Ciclos de cache ineficientes" do PageSpeed
        if request.path.startswith('/static/'):
            response.cache_control.max_age = 31536000  # 1 ano em segundos
            response.cache_control.public = True
        return response

    # =========================================================
    # INICIALIZAÇÃO DO CACHE (Ajuste para Render)
    # =========================================================
    try:
        app.config['CACHE_TYPE'] = 'SimpleCache'
        app.config['CACHE_DEFAULT_TIMEOUT'] = 300
        cache.init_app(app)
        app.logger.info("[CACHE] Sistema de cache inicializado.")
    except Exception as e:
        app.logger.warning(f"[CACHE] Erro ao inicializar cache: {e}")

    # =========================================================
    # REGISTRO DE BLUEPRINTS
    # =========================================================
    from app.main import main
    from app.admin import admin_bp
    from app.clientes.routes import clientes_bp
    from app.vendas import vendas_bp
    from app.vendas.routes.sales_core import sales_core
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
    from app.certidoes import certidoes_bp
    from app.loja import loja_bp
    from app.loja_admin import loja_admin_bp
    from app.carrinho import carrinho_bp
    
    app.register_blueprint(uploads_bp, url_prefix="/uploads")
    app.register_blueprint(main)
    app.register_blueprint(clientes_bp, url_prefix="/clientes")
    app.register_blueprint(produtos_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(configs_bp)
    app.register_blueprint(loja_bp)
    app.register_blueprint(carrinho_bp, url_prefix='/carrinho')
    app.register_blueprint(loja_admin_bp, url_prefix="/admin-loja")
    app.register_blueprint(vendas_bp, url_prefix="/vendas")
    app.register_blueprint(sales_core, url_prefix="/vendas")
    app.register_blueprint(categorias_bp)
    app.register_blueprint(taxas_bp)
    app.register_blueprint(pedidos_bp, url_prefix="/pedidos")
    app.register_blueprint(alertas_bp)
    app.register_blueprint(notificacoes_bp)
    app.register_blueprint(compras_nf_bp)
    app.register_blueprint(importacoes_bp)
    app.register_blueprint(certidoes_bp, url_prefix="/certidoes")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # =========================================================
    # AGENDADOR DE TAREFAS
    # =========================================================
    from app.alertas.tasks import iniciar_scheduler
    iniciar_scheduler(app)

    # =========================================================
    # FILTROS E CONTEXTO JINJA (Fotos, Moedas e Datas)
    # =========================================================
    
    @app.template_filter('currency')
    @app.template_filter('formato_moeda')
    def format_currency(value):
        if value is None or isinstance(value, Undefined):
            return "R$ 0,00"
        try:
            v = float(value)
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    from datetime import timezone
    import pytz

    @app.template_filter('dt_local')
    def format_datetime_local(dt, fmt="%d/%m/%Y %H:%M", tzname="America/Fortaleza"):
        if not dt: return ""
        try:
            tz = pytz.timezone(tzname)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(tz).strftime(fmt)
        except Exception:
            return str(dt)

    @app.context_processor
    def inject_global_utilities():
        """Centraliza utilitários globais em todos os templates."""
        from app.utils.r2_helpers import gerar_link_r2
        
        def limpar_caminho_r2(caminho):
            if not caminho: return ""
            bucket_nome = "m4-clientes-docs"
            caminho_limpo = caminho.replace(f"/{bucket_nome}", "").replace(bucket_nome, "")
            caminho_limpo = caminho_limpo.replace("//", "/").lstrip("/")
            return caminho_limpo.split("#")[0].split("%23")[0]

        def gerar_link_global(path):
            if not path: return "/static/img/placeholder.jpg"
            return gerar_link_r2(limpar_caminho_r2(path))

        return {
            "now_local": now_local,
            "gerar_link": gerar_link_global
        }

    # =========================================================
    # SEED INICIAL (MODO PROTEGIDO)
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
                    taxas_padrao = [Taxa(numero_parcelas=i, juros=1.0) for i in range(13)]
                    db.session.add_all(taxas_padrao)

                Configuracao.seed_defaults()
                db.session.commit()

    return app