from flask import Blueprint

compras_nf_bp = Blueprint(
    "compras_nf",
    __name__,
    url_prefix="/compras",
    template_folder="templates"
)

from app.compras import routes