# ======================
# MÓDULO DE ALERTAS
# ======================

from flask import Blueprint

# Criação do Blueprint principal
alertas_bp = Blueprint(
    "alertas",
    __name__,
    template_folder="templates",
    static_folder="static"
)

from app.alertas import routes  # noqa: E402
