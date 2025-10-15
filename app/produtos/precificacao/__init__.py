from flask import Blueprint

precificacao_bp = Blueprint("precificacao", __name__, url_prefix="/precificacao", template_folder="templates", static_folder="static")
