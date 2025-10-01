from flask import Blueprint

pedidos_bp = Blueprint("pedidos", __name__)

from app.pedidos import routes  # importa rotas
