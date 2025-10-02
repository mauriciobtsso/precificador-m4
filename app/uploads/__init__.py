from flask import Blueprint

uploads_bp = Blueprint("uploads", __name__, url_prefix="/uploads")

from app.uploads import routes  # noqa
