from flask import render_template, request, redirect, url_for, flash
from app import db
from app.clientes import clientes_bp
from app.clientes.models import Cliente, Processo
from app.utils.datetime import now_local


# =================================================
# NOVO PROCESSO
# =================================================
@clientes_bp.route("/<int:cliente_id>/processos/novo", methods=["GET", "POST"])
def novo_processo(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        tipo = request.form.get("tipo")
        status = request.form.get("status")
        descricao = request.form.get("descricao")

        if not tipo or not status:
            flash("Preencha todos os campos obrigatórios do processo.", "warning")
            return redirect(url_for("clientes.novo_processo", cliente_id=cliente.id))

        processo = Processo(
            cliente_id=cliente.id,
            tipo=tipo,
            status=status,
            descricao=descricao,
            data=now_local(),
        )
        db.session.add(processo)
        db.session.commit()
        flash("Processo cadastrado com sucesso!", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

    return render_template("clientes/novo_processo.html", cliente=cliente, now=now_local())


# =================================================
# EDITAR PROCESSO
# =================================================
@clientes_bp.route("/<int:cliente_id>/processos/<int:proc_id>/editar", methods=["GET", "POST"])
def editar_processo(cliente_id, proc_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    processo = Processo.query.get_or_404(proc_id)

    if request.method == "POST":
        processo.tipo = request.form.get("tipo")
        processo.status = request.form.get("status")
        processo.descricao = request.form.get("descricao")

        db.session.commit()
        flash("Processo atualizado com sucesso!", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

    return render_template(
        "clientes/editar_processo.html",
        cliente=cliente,
        processo=processo
    )


# =================================================
# EXCLUIR PROCESSO
# =================================================
@clientes_bp.route("/<int:cliente_id>/processos/<int:proc_id>/excluir", methods=["POST"])
def excluir_processo(cliente_id, proc_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    processo = Processo.query.get_or_404(proc_id)

    db.session.delete(processo)
    db.session.commit()
    flash("Processo excluído com sucesso!", "success")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))
