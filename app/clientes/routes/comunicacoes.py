from flask import render_template, redirect, url_for
from app.clientes import clientes_bp
from app.clientes.models import Cliente, Comunicacao


# =================================================
# ABA COMUNICAÇÕES (renderização)
# =================================================
@clientes_bp.route("/<int:cliente_id>/comunicacoes", methods=["GET", "POST"])
def cliente_comunicacoes(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template("clientes/abas/comunicacoes.html", cliente=cliente)


# =================================================
# RETROCOMPATIBILIDADE (antigo "/nova")
# =================================================
@clientes_bp.route("/<int:cliente_id>/comunicacoes/nova", methods=["POST"])
def nova_comunicacao(cliente_id):
    return cliente_comunicacoes(cliente_id)
