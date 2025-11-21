from flask import render_template, request, redirect, url_for, flash
from app import db
from app.utils.db_helpers import get_or_404
from app.clientes import clientes_bp
from app.clientes.models import ContatoCliente, Cliente


# =================================================
# ADICIONAR CONTATO
# =================================================
@clientes_bp.route("/<int:cliente_id>/contatos/adicionar", methods=["POST"])
def adicionar_contato(cliente_id):
    cliente = get_or_404(Cliente, cliente_id)
    try:
        contato = ContatoCliente(
            cliente_id=cliente.id,
            tipo=request.form.get("tipo"),
            valor=request.form.get("valor")
        )
        db.session.add(contato)
        db.session.commit()
        flash("Contato adicionado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao adicionar contato: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


# =================================================
# EDITAR CONTATO
# =================================================
@clientes_bp.route("/<int:cliente_id>/contatos/<int:contato_id>/editar", methods=["GET", "POST"])
def editar_contato(cliente_id, contato_id):
    contato = get_or_404(ContatoCliente, contato_id)

    if request.method == "POST":
        try:
            contato.tipo = request.form.get("tipo")
            contato.valor = request.form.get("valor")
            db.session.commit()
            flash("Contato atualizado com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar contato: {e}", "danger")

    return render_template(
        "clientes/editar_contato.html",
        cliente_id=cliente_id,
        contato=contato
    )


# =================================================
# DELETAR CONTATO
# =================================================
@clientes_bp.route("/<int:cliente_id>/contatos/<int:contato_id>/delete", methods=["POST"])
def deletar_contato(cliente_id, contato_id):
    contato = get_or_404(ContatoCliente, contato_id)
    try:
        db.session.delete(contato)
        db.session.commit()
        flash("Contato excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir contato: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))
