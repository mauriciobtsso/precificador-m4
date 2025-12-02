from flask import Blueprint

vendas_bp = Blueprint(
    "vendas", 
    __name__, 
    template_folder="templates",
    # 🚨 CORREÇÃO: Adicionando a pasta estática local
    static_folder="static",
    # O url_path garante que os arquivos sejam referenciados via /vendas/static/...
    static_url_path="/vendas/static" 
)

from . import routes