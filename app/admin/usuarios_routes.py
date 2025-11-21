# app/admin/usuarios_routes.py

from flask import (
    render_template, request, redirect,
    url_for, flash
)
from flask_login import login_required
from app.extensions import db
from app.models import User
from app.admin import admin_bp


# ---------------------------
# Lista de Usuários
# ---------------------------
@admin_bp.route("/usuarios")
@login_required
def usuarios():
    users = User.query.all()
    return render_template("admin/usuarios.html", users=users)


# ---------------------------
# Criar / Editar Usuário
# ---------------------------
@admin_bp.route("/usuario/novo", methods=["GET", "POST"])
@admin_bp.route("/usuario/editar/<int:user_id>", methods=["GET", "POST"])
@login_required
def gerenciar_usuario(user_id=None):
    user = User.query.get(user_id) if user_id else None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not user:
            # Novo usuário
            user = User(username=username)
            if password:
                user.set_password(password)
            db.session.add(user)
        else:
            # Editar usuário
            user.username = username
            if password:
                user.set_password(password)

        db.session.commit()
        flash("Usuário salvo com sucesso!", "success")
        return redirect(url_for("admin.usuarios"))

    return render_template("admin/usuario_form.html", user=user)


# ---------------------------
# Excluir Usuário
# ---------------------------
@admin_bp.route("/usuario/excluir/<int:user_id>")
@login_required
def excluir_usuario(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()

    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("admin.usuarios"))
