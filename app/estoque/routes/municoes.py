from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from app.clientes.models import Cliente
from datetime import datetime

# ================================
# LISTAGEM — MUNIÇÕES
# ================================
@estoque_bp.route("/municoes")
@login_required
def municoes_listar():
    itens = (
        ItemEstoque.query.filter_by(tipo_item="municao")
        .order_by(ItemEstoque.data_entrada.desc())
        .all()
    )
    return render_template("estoque/municoes/listar.html", itens=itens)


# ================================
# NOVA ENTRADA — MUNIÇÃO
# ================================
@estoque_bp.route("/municoes/novo", methods=["GET", "POST"])
@login_required
def municoes_novo():
    produtos = Produto.query.order_by(Produto.nome).all()
    fornecedores = Cliente.query.all()

    if request.method == "POST":
        try:
            item = ItemEstoque(
                tipo_item="municao",
                produto_id=request.form.get("produto_id"),
                fornecedor_id=request.form.get("fornecedor_id"),
                lote=request.form.get("lote"),
                numero_embalagem=request.form.get("numero_embalagem"),
                quantidade=request.form.get("quantidade") or 1,
                status=request.form.get("status") or "disponivel",
                data_entrada=request.form.get("data_entrada") or datetime.utcnow(),
                observacoes=request.form.get("observacoes"),
            )
            db.session.add(item)
            db.session.commit()
            flash("✅ Munição adicionada ao estoque com sucesso!", "success")
            return redirect(url_for("estoque.municoes_listar"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Erro ao salvar: {e}", "danger")

    return render_template(
        "estoque/municoes/form.html",
        produtos=produtos,
        fornecedores=fornecedores,
        tipo_item="municao",
    )
