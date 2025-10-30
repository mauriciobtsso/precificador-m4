from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from app.clientes.models import Cliente
from datetime import datetime

# ================================
# LISTAGEM — NÃO CONTROLADOS
# ================================
@estoque_bp.route("/nao_controlados")
@login_required
def nao_controlados_listar():
    itens = (
        ItemEstoque.query.filter_by(tipo_item="nao_controlado")
        .order_by(ItemEstoque.data_entrada.desc())
        .all()
    )
    return render_template("estoque/nao_controlados/listar.html", itens=itens)


# ================================
# NOVA ENTRADA — NÃO CONTROLADO
# ================================
@estoque_bp.route("/nao_controlados/novo", methods=["GET", "POST"])
@login_required
def nao_controlados_novo():
    produtos = Produto.query.order_by(Produto.nome).all()
    fornecedores = Cliente.query.all()

    if request.method == "POST":
        try:
            item = ItemEstoque(
                tipo_item="nao_controlado",
                produto_id=request.form.get("produto_id"),
                fornecedor_id=request.form.get("fornecedor_id"),
                quantidade=request.form.get("quantidade") or 1,
                status=request.form.get("status") or "disponivel",
                data_entrada=request.form.get("data_entrada") or datetime.utcnow(),
                observacoes=request.form.get("observacoes"),
            )
            db.session.add(item)
            db.session.commit()
            flash("✅ Produto não controlado adicionado ao estoque!", "success")
            return redirect(url_for("estoque.nao_controlados_listar"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Erro ao salvar: {e}", "danger")

    return render_template(
        "estoque/nao_controlados/form.html",
        produtos=produtos,
        fornecedores=fornecedores,
        tipo_item="nao_controlado",
    )
