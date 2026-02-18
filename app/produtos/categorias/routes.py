# ======================
# ROTAS — CATEGORIAS DE PRODUTOS (ESTILO MAHRTE)
# ======================

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
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
    # Ordenamos pela 'ordem_exibicao' para respeitar a hierarquia visual do site
    categorias_pai = CategoriaProduto.query.filter_by(pai_id=None).order_by(CategoriaProduto.ordem_exibicao.asc(), CategoriaProduto.nome.asc()).all()
    return render_template("categorias/categorias.html", categorias_pai=categorias_pai)

# ======================
# API: Adicionar categoria via AJAX (modal no form de produto)
# ======================
@categorias_bp.route("/nova/ajax", methods=["POST"])
@login_required
def adicionar_categoria_ajax():
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
        return jsonify({"id": nova_cat.id, "nome": nova_cat.nome, "slug": nova_cat.slug})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao criar categoria via AJAX: {e}")
        return jsonify({"erro": "Erro interno ao salvar."}), 500


# ======================
# NOVA / EDITAR (FORMULÁRIO COMPLETO)
# ======================
@categorias_bp.route("/nova", methods=["GET", "POST"])
@categorias_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_categoria(id=None):
    categoria = CategoriaProduto.query.get(id) if id else None
    # Busca categorias pai para o dropdown de hierarquia
    categorias_pai = CategoriaProduto.query.filter_by(pai_id=None).order_by(CategoriaProduto.nome).all()

    if request.method == "POST":
        data = request.form
        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        pai_id_raw = data.get("pai_id")
        icone_loja = data.get("icone_loja", "").strip()
        ordem_raw = data.get("ordem_exibicao", 0)
        
        # Coleta a flag de exibição (checkbox HTML envia 'on' se marcado)
        exibir_check = request.form.get("exibir_no_menu") == "on"

        if not nome:
            flash("O nome da categoria é obrigatório.", "warning")
            return redirect(request.url)

        try:
            # Se for nova categoria, instancia
            if not categoria:
                categoria = CategoriaProduto(nome=nome)
                db.session.add(categoria)

            # Atribuição de valores com tratamento de tipos
            categoria.nome = nome
            categoria.descricao = descricao or None
            categoria.icone_loja = icone_loja or None
            categoria.exibir_no_menu = exibir_check
            
            # Tratamento seguro para IDs e Ordem (evita erro de string vazia)
            try:
                categoria.pai_id = int(pai_id_raw) if pai_id_raw else None
            except (ValueError, TypeError):
                categoria.pai_id = None
                
            try:
                categoria.ordem_exibicao = int(ordem_raw)
            except (ValueError, TypeError):
                categoria.ordem_exibicao = 0

            db.session.commit()
            flash("✅ Categoria salva com sucesso!", "success")
            return redirect(url_for("categorias.index"))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar categoria: {e}")
            flash(f"❌ Erro ao salvar categoria: {str(e)}", "danger")

    return render_template("categorias/categoria_form.html", categoria=categoria, categorias_pai=categorias_pai)

# ======================
# EXCLUIR
# ======================
@categorias_bp.route("/<int:id>/excluir")
@login_required
def excluir_categoria(id):
    categoria = CategoriaProduto.query.get_or_404(id)

    if categoria.subcategorias:
        flash("⚠️ Não é possível excluir uma categoria que possui subcategorias.", "warning")
        return redirect(url_for("categorias.index"))

    try:
        db.session.delete(categoria)
        db.session.commit()
        flash("🗑️ Categoria excluída com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir categoria: {e}")
        flash("❌ Erro ao excluir categoria. Verifique se existem produtos vinculados.", "danger")
        
    return redirect(url_for("categorias.index"))