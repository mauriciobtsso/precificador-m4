from flask import Blueprint

# Define o blueprint do módulo Clientes
# Todas as rotas relacionadas a clientes, documentos e armas
# ficam em app/clientes/routes.py
clientes_bp = Blueprint(
    "clientes",
    __name__,
    template_folder="templates",
    static_folder="static"
)

# Importa as rotas do módulo (mantém no final para evitar import circular)
from app.clientes import routes  # noqa: E402, F401
