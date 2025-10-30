from flask import Blueprint

estoque_bp = Blueprint(
    "estoque",
    __name__,
    url_prefix="/estoque",
    template_folder="templates",
    static_folder="static"
)

# importa sub-rotas (modulares)
from app.estoque.routes import *  # noqa
