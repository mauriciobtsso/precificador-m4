from flask import Blueprint

# Define o blueprint principal da aplicação
# Todas as rotas gerais (dashboard, produtos, taxas, usuários, pedidos, etc.)
# ficam em app/main/routes.py
main = Blueprint("main", __name__, template_folder="templates")

# Importa as rotas (necessário para registrar no blueprint)
from app.main import routes  # noqa: E402, F401
