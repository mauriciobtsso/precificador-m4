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

# ⚠️ IMPORTANTE:
# Esse import deve vir DEPOIS da criação do blueprint,
# pois é ele que faz o Flask registrar todas as rotas (como /novo e /editar)
try:
    from app.produtos import routes  # noqa: E402, F401
except Exception as e:
    print(f"[AVISO] Não foi possível importar app.produtos.routes: {e}")
