from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from app.clientes.models import Cliente
from datetime import datetime

# ================================
# LISTAGEM — ARMAS
# ================================
@estoque_bp.route("/armas")
@login_required
def armas_listar():
    itens = (
        ItemEstoque.query.filter_by(tipo_item="arma")
        .order_by(ItemEstoque.data_entrada.desc())
        .all()
    )
    return render_template("estoque/armas/listar.html", itens=itens)


# ================================
# NOVA ENTRADA — ARMA
# ================================
@estoque_bp.route("/armas/novo", methods=["GET", "POST"])
@login_required
def armas_novo():
    produtos = Produto.query.order_by(Produto.nome).all()
    fornecedores = Cliente.query.all()

    if request.method == "POST":
        try:
            item = ItemEstoque(
                tipo_item="arma",
                produto_id=request.form.get("produto_id"),
                fornecedor_id=request.form.get("fornecedor_id"),
                numero_serie=request.form.get("numero_serie"),
                status=request.form.get("status") or "disponivel",
                data_entrada=request.form.get("data_entrada") or datetime.utcnow(),
                observacoes=request.form.get("observacoes"),
            )
            db.session.add(item)
            db.session.commit()
            flash("✅ Arma adicionada ao estoque com sucesso!", "success")
            return redirect(url_for("estoque.armas_listar"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Erro ao salvar: {e}", "danger")

    return render_template(
        "estoque/armas/form.html",
        produtos=produtos,
        fornecedores=fornecedores,
        tipo_item="arma",
    )
