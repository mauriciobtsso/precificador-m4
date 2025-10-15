# ======================
# NOTIFICAÇÕES - BLUEPRINT
# ======================

from flask import Blueprint

notificacoes_bp = Blueprint(
    "notificacoes",
    __name__,
    url_prefix="/notificacoes"
)

from app.notificacoes import routes  # noqa: E402, F401
