"""Read-only API for sharing the public store catalog with trusted clients."""

from flask import Blueprint

catalog_api_bp = Blueprint(
    "catalog_api",
    __name__,
    url_prefix="/api/v1/catalogo",
)

from app.catalog_api import routes  # noqa: E402,F401
