# ======================
# ROTAS — CATEGORIAS DE PRODUTOS (com hierarquia)
# ======================

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app import db
from app.produtos.categorias.models import CategoriaProduto

categorias_bp = Blueprint(
    "categorias",
    __name__,
    url_prefix="/produtos/categorias",
    template_folder="templates",
    static_folder="static"
)

# ======================
# LISTAGEM
# ======================
@categorias_bp.route("/")
@login_required
def index():
    categorias_pai = CategoriaProduto.query.filter_by(pai_id=None).order_by(CategoriaProduto.nome.asc()).all()
    return render_template("categorias/categorias.html", categorias_pai=categorias_pai)

# ======================
# API: Adicionar categoria via AJAX (modal)
# ======================
@categorias_bp.route("/nova", methods=["POST"])
@login_required
def adicionar_categoria_ajax():
    from flask import request, jsonify
    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    pai_id = data.get("pai_id")
    descricao = (data.get("descricao") or "").strip() or None

    if not nome:
        return jsonify({"erro": "Nome é obrigatório."}), 400

    nova_cat = CategoriaProduto(nome=nome, descricao=descricao)
    if pai_id:
        try:
            nova_cat.pai_id = int(pai_id)
        except (ValueError, TypeError):
            pass

    try:
        db.session.add(nova_cat)
        db.session.commit()
        return jsonify({"id": nova_cat.id, "nome": nova_cat.nome})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao criar categoria via AJAX: {e}")
        return jsonify({"erro": "Erro interno ao salvar."}), 500


# ======================
# NOVA / EDITAR
# ======================
@categorias_bp.route("/nova", methods=["GET", "POST"])
@categorias_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_categoria(id=None):
    categoria = CategoriaProduto.query.get(id) if id else None
    categorias_pai = CategoriaProduto.query.filter_by(pai_id=None).order_by(CategoriaProduto.nome).all()

    if request.method == "POST":
        data = request.form
        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        pai_id = data.get("pai_id") or None

        if not nome:
            flash("O nome da categoria é obrigatório.", "warning")
            return redirect(request.url)

        try:
            if not categoria:
                categoria = CategoriaProduto(nome=nome)
                db.session.add(categoria)

            categoria.nome = nome
            categoria.descricao = descricao or None
            categoria.pai_id = int(pai_id) if pai_id else None

            db.session.commit()
            flash("Categoria salva com sucesso!", "success")
            return redirect(url_for("categorias.index"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar categoria: {e}")
            flash("Erro ao salvar categoria.", "danger")

    return render_template("categorias/categoria_form.html", categoria=categoria, categorias_pai=categorias_pai)

# ======================
# EXCLUIR
# ======================
@categorias_bp.route("/<int:id>/excluir")
@login_required
def excluir_categoria(id):
    categoria = CategoriaProduto.query.get_or_404(id)

    if categoria.subcategorias:
        flash("Não é possível excluir uma categoria que possui subcategorias.", "warning")
        return redirect(url_for("categorias.index"))

    db.session.delete(categoria)
    db.session.commit()
    flash("Categoria excluída com sucesso.", "success")
    return redirect(url_for("categorias.index"))
