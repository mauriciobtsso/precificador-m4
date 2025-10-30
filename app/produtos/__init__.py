# ======================
# MÓDULO: PRODUTOS
# ======================

from flask import Blueprint

# Cria o blueprint principal do módulo
produtos_bp = Blueprint(
    "produtos",
    __name__,
    url_prefix="/produtos",
    template_folder="templates",
    static_folder="static"
)

# ⚙️ IMPORTANTE:
# Os imports devem vir DEPOIS da criação do blueprint
# e DEVE SER RELATIVO para evitar duplicação de módulos no SQLAlchemy
try:
    from .routes import main, fotos, historico, autosave, tecnicos
except Exception as e:
    print(f"[AVISO] Falha ao importar submódulos de produtos: {e}")
