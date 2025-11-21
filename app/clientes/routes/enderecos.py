from flask import render_template, request, redirect, url_for, flash
from app import db
from app.utils.db_helpers import get_or_404
from app.clientes import clientes_bp
from app.clientes.models import EnderecoCliente, Cliente


# =================================================
# ADICIONAR ENDEREÇO
# =================================================
@clientes_bp.route("/<int:cliente_id>/enderecos/adicionar", methods=["POST"])
def adicionar_endereco(cliente_id):
    cliente = get_or_404(Cliente, cliente_id)
    try:
        endereco = EnderecoCliente(
            cliente_id=cliente.id,
            logradouro=request.form.get("logradouro"),
            numero=request.form.get("numero"),
            complemento=request.form.get("complemento"),
            bairro=request.form.get("bairro"),
            cidade=request.form.get("cidade"),
            estado=request.form.get("estado"),
            cep=request.form.get("cep"),
            tipo=request.form.get("tipo"),
        )
        db.session.add(endereco)
        db.session.commit()
        flash("Endereço adicionado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao adicionar endereço: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


# =================================================
# EDITAR ENDEREÇO
# =================================================
@clientes_bp.route("/<int:cliente_id>/enderecos/<int:endereco_id>/editar", methods=["GET", "POST"])
def editar_endereco(cliente_id, endereco_id):
    endereco = get_or_404(EnderecoCliente, endereco_id)

    if request.method == "POST":
        try:
            endereco.logradouro = request.form.get("logradouro")
            endereco.numero = request.form.get("numero")
            endereco.complemento = request.form.get("complemento")
            endereco.bairro = request.form.get("bairro")
            endereco.cidade = request.form.get("cidade")
            endereco.estado = request.form.get("estado")
            endereco.cep = request.form.get("cep")
            endereco.tipo = request.form.get("tipo")
            db.session.commit()
            flash("Endereço atualizado com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar endereço: {e}", "danger")

    return render_template(
        "clientes/editar_endereco.html",
        cliente_id=cliente_id,
        endereco=endereco
    )


# =================================================
# DELETAR ENDEREÇO
# =================================================
@clientes_bp.route("/<int:cliente_id>/enderecos/<int:endereco_id>/delete", methods=["POST"])
def deletar_endereco(cliente_id, endereco_id):
    endereco = get_or_404(EnderecoCliente, endereco_id)
    try:
        db.session.delete(endereco)
        db.session.commit()
        flash("Endereço excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir endereço: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))
