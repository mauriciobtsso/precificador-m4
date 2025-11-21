# app/admin/routes.py

from flask import render_template
from flask_login import login_required
from app.admin import admin_bp

@admin_bp.route("/")
@login_required
def index():
    return render_template("admin/index_placeholder.html")
