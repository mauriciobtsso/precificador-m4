# app/clientes/routes/loja_acesso.py
"""
Rotas administrativas para gerenciar o acesso de clientes à loja.
Registradas no clientes_bp — acessíveis apenas pelo back-end admin.
"""

from flask import request, redirect, url_for, flash, render_template
from app import db
from app.clientes import clientes_bp
from app.clientes.models import Cliente
from app.utils.datetime import now_local


# ─────────────────────────────────────────────
# LIBERAR ACESSO À LOJA (pelo admin)
# ─────────────────────────────────────────────
@clientes_bp.route("/<int:cliente_id>/loja/liberar", methods=["POST"])
def liberar_acesso_loja(cliente_id):
    """
    O admin define um e-mail de login e senha temporária para o cliente.
    O cliente acessa a loja e encontra tudo que já tinha: documentos,
    endereços, armas, histórico de compras.
    """
    cliente = Cliente.query.get_or_404(cliente_id)

    email    = (request.form.get("email_login") or "").strip().lower()
    senha    = request.form.get("senha_temp") or ""

    if not email or not senha:
        flash("Informe o e-mail e a senha temporária.", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

    if len(senha) < 6:
        flash("A senha temporária deve ter pelo menos 6 caracteres.", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

    # Verifica se o e-mail já está em uso por outro cliente
    existente = Cliente.query.filter(
        Cliente.email_login == email,
        Cliente.id != cliente_id
    ).first()

    if existente:
        flash(f"Este e-mail já está em uso pelo cliente #{existente.id}.", "danger")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

    cliente.email_login    = email
    cliente.ativo_loja     = True
    cliente.loja_criado_em = cliente.loja_criado_em or now_local()
    cliente.set_senha(senha)

    db.session.commit()

    flash(
        f"Acesso liberado! Cliente pode entrar com {email} e a senha temporária informada.",
        "success"
    )
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))


# ─────────────────────────────────────────────
# REVOGAR ACESSO À LOJA
# ─────────────────────────────────────────────
@clientes_bp.route("/<int:cliente_id>/loja/revogar", methods=["POST"])
def revogar_acesso_loja(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.ativo_loja = False
    db.session.commit()
    flash("Acesso à loja revogado.", "warning")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))


# ─────────────────────────────────────────────
# REATIVAR ACESSO
# ─────────────────────────────────────────────
@clientes_bp.route("/<int:cliente_id>/loja/reativar", methods=["POST"])
def reativar_acesso_loja(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if not cliente.email_login:
        flash("Cliente não tem e-mail de login cadastrado. Libere o acesso primeiro.", "warning")
    else:
        cliente.ativo_loja = True
        db.session.commit()
        flash("Acesso à loja reativado.", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))