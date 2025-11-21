# app/admin/config_routes.py

from flask import (
    render_template, request, redirect,
    url_for, flash
)
from flask_login import login_required
from app.extensions import db
from app.models import Configuracao
from app.admin import admin_bp


@admin_bp.route("/configuracoes")
@login_required
def configuracoes():
    configs = Configuracao.query.all()
    return render_template("admin/configuracoes.html", configs=configs)


@admin_bp.route("/configuracao/nova", methods=["GET", "POST"])
@admin_bp.route("/configuracao/editar/<int:config_id>", methods=["GET", "POST"])
@login_required
def gerenciar_configuracao(config_id=None):
    config = Configuracao.query.get(config_id) if config_id else None

    if request.method == "POST":
        chave = request.form.get("chave")
        valor = request.form.get("valor")

        if not config:
            config = Configuracao(chave=chave, valor=valor)
            db.session.add(config)
        else:
            config.chave = chave
            config.valor = valor

        db.session.commit()
        flash("Configuração salva com sucesso!", "success")
        return redirect(url_for("admin.configuracoes"))

    return render_template("admin/configuracao_form.html", config=config)


@admin_bp.route("/configuracao/excluir/<int:config_id>")
@login_required
def excluir_configuracao(config_id):
    config = Configuracao.query.get_or_404(config_id)
    db.session.delete(config)
    db.session.commit()

    flash("Configuração excluída com sucesso!", "success")
    return redirect(url_for("admin.configuracoes"))
