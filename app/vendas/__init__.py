from flask import Blueprint

vendas_bp = Blueprint("vendas", __name__, template_folder="templates")

from . import routes
