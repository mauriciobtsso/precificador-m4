# ============================================================
# app/importacoes/__init__.py
# ============================================================

from flask import Blueprint

# Blueprint principal do módulo de Importações
importacoes_bp = Blueprint(
    "importacoes",
    __name__,
    url_prefix="/importacoes",
    template_folder="templates",
    static_folder="static"
)

# Importa as rotas após definir o blueprint
from app.importacoes import routes
