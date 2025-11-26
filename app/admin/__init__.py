# app/admin/__init__.py

from flask import Blueprint

admin_bp = Blueprint(
    "admin",
    __name__,
    template_folder="templates",
    static_folder="static"
)

from app.admin import routes
from app.admin import usuarios_routes
from app.admin import config_routes
from app.admin import documentos_routes