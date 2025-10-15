# ======================
# ROTAS — PRODUTOS
# ======================

from flask import (
    render_template, request, redirect, url_for,
    flash, jsonify, current_app, send_file
)
from flask_login import login_required
from werkzeug.utils import secure_filename
from app import db
from app.produtos import produtos_bp
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.utils.importar import importar_planilha_produtos
from decimal import Decimal
import io


# ======================
# LISTAGEM DE PRODUTOS
# ======================
@produtos_bp.route("/", endpoint="index")
@login_required
def index():
    termo = request.args.get("termo", "").strip()
    lucro = request.args.get("lucro", "")
    preco_min = request.args.get("preco_min", type=float)
    preco_max = request.args.get("preco_max", type=float)

    query = Produto.query

    # 🔍 Filtros opcionais
    if termo:
        query = query.filter(Produto.nome.ilike(f"%{termo}%"))
    if preco_min:
        query = query.filter(Produto.preco >= preco_min)
    if preco_max:
        query = query.filter(Produto.preco <= preco_max)

    produtos = query.all()
    return render_template("produtos/index.html", produtos=produtos)

# ======================
# IMPORTAR PRODUTOS VIA PLANILHA
# ======================
@produtos_bp.route("/importar", methods=["GET", "POST"])
@login_required
def importar_produtos():
    """Importa produtos a partir de uma planilha Excel/CSV."""
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if not arquivo:
            flash("Nenhum arquivo selecionado.", "warning")
            return redirect(url_for("produtos.importar_produtos"))

        try:
            # Aqui você pode usar sua função de importação existente
            from app.services.importacao import importar_produtos_planilha
            qtd, erros = importar_produtos_planilha(arquivo)

            flash(f"✅ {qtd} produtos importados com sucesso!", "success")
            if erros:
                flash(f"⚠️ Alguns produtos apresentaram erros: {', '.join(erros)}", "warning")

        except Exception as e:
            current_app.logger.error(f"Erro ao importar produtos: {e}")
            flash("❌ Erro ao processar a planilha de produtos.", "danger")

        return redirect(url_for("produtos.index"))

    # GET → exibe formulário simples de upload
    return render_template("produtos/importar.html")



# ======================
# CADASTRAR / EDITAR PRODUTO
# ======================
@produtos_bp.route("/novo", methods=["GET", "POST"])
@produtos_bp.route("/<int:produto_id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_produto(produto_id=None):
    """Cria ou edita um produto com validação de duplicidade e categoria."""

    # 🔁 DUPLICAR PRODUTO (pré-preenche o formulário)
    duplicar_de = request.args.get("duplicar_de", type=int)
    if duplicar_de:
        produto_ref = Produto.query.get(duplicar_de)
        if produto_ref:
            produto = Produto(
                nome=produto_ref.nome,
                descricao=produto_ref.descricao,
                categoria_id=produto_ref.categoria_id,
                preco_fornecedor=produto_ref.preco_fornecedor,
                desconto_fornecedor=produto_ref.desconto_fornecedor,
                frete=produto_ref.frete,
                margem=produto_ref.margem,
                lucro_alvo=produto_ref.lucro_alvo,
                preco_final=produto_ref.preco_final,
                ipi_tipo=produto_ref.ipi_tipo,
                ipi=produto_ref.ipi,
                difal=produto_ref.difal,
                imposto_venda=produto_ref.imposto_venda,
            )
            flash(f"Produto '{produto_ref.nome}' duplicado. Revise antes de salvar.", "info")
        else:
            flash("⚠️ Produto de origem não encontrado para duplicação.", "warning")
            produto = Produto()
    else:
        produto = Produto.query.get(produto_id) if produto_id else Produto()

    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()

    if request.method == "POST":
        data = request.form

        # Campos principais
        codigo = (data.get("codigo") or "").strip().upper()
        nome = (data.get("nome") or "").strip()
        descricao = (data.get("descricao") or "").strip() or None

        # Categoria
        cat_id = data.get("categoria_id")
        categoria_id = int(cat_id) if cat_id else None

        # 🚫 Verifica duplicidade (ignora o próprio produto)
        existente = (
            Produto.query.filter(Produto.codigo == codigo)
            .filter(Produto.id != produto.id if produto.id else True)
            .first()
        )
        if existente:
            flash(f"⚠️ Já existe um produto com o código {codigo}.", "warning")
            return redirect(url_for("produtos.gerenciar_produto", produto_id=produto.id))

        # Atualiza ou cria
        produto.codigo = codigo
        produto.nome = nome
        produto.descricao = descricao
        produto.categoria_id = categoria_id

        # Conversão segura para Decimal
        from decimal import Decimal, InvalidOperation

        def to_decimal(value):
            try:
                return Decimal(str(value or 0).replace(",", "."))
            except InvalidOperation:
                return Decimal(0)

        produto.preco_fornecedor = to_decimal(data.get("preco_fornecedor"))
        produto.desconto_fornecedor = to_decimal(data.get("desconto_fornecedor"))
        produto.frete = to_decimal(data.get("frete"))
        produto.margem = to_decimal(data.get("margem"))
        produto.lucro_alvo = to_decimal(data.get("lucro_alvo"))
        produto.preco_final = to_decimal(data.get("preco_final"))
        produto.ipi = to_decimal(data.get("ipi"))
        produto.difal = to_decimal(data.get("difal"))
        produto.imposto_venda = to_decimal(data.get("imposto_venda"))
        produto.ipi_tipo = data.get("ipi_tipo", "%_dentro")

        try:
            if hasattr(produto, "calcular_precos"):
                produto.calcular_precos()

            db.session.add(produto)
            db.session.commit()

            flash("✅ Produto salvo com sucesso!", "success")
            return redirect(url_for("produtos.index"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar produto: {e}")
            flash("❌ Ocorreu um erro ao salvar o produto.", "danger")

    # GET
    return render_template("produtos/produto_form.html", produto=produto, categorias=categorias)


# ======================
# EXCLUIR PRODUTO
# ======================
@produtos_bp.route("/<int:produto_id>/excluir")
@login_required
def excluir_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    try:
        db.session.delete(produto)
        db.session.commit()
        flash("🗑️ Produto excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir produto: {e}")
        flash("❌ Erro ao excluir produto.", "danger")
    return redirect(url_for("produtos.index"))

# ======================
# DUPLICAR PRODUTO
# ======================

from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.produtos.models import Produto, CategoriaProduto

produtos_bp = Blueprint("produtos", __name__)

@produtos_bp.route("/<int:produto_id>/duplicar")
@login_required
def duplicar_produto(produto_id):
    """Duplica um produto existente, abrindo o form pré-preenchido para revisão."""
    produto_original = Produto.query.get_or_404(produto_id)

    # Cria uma cópia do objeto (sem ID e código)
    produto_novo = Produto(
        codigo=None,  # o usuário define no form
        sku=None,
        nome=produto_original.nome,
        descricao=produto_original.descricao,
        categoria_id=produto_original.categoria_id,
        preco_fornecedor=produto_original.preco_fornecedor,
        desconto_fornecedor=produto_original.desconto_fornecedor,
        frete=produto_original.frete,
        margem=produto_original.margem,
        lucro_alvo=produto_original.lucro_alvo,
        preco_final=produto_original.preco_final,
        ipi_tipo=produto_original.ipi_tipo,
        ipi=produto_original.ipi,
        difal=produto_original.difal,
        imposto_venda=produto_original.imposto_venda,
    )

    # ⚠️ Não comita ainda — apenas cria a instância para edição
    db.session.expunge(produto_original)  # evita vínculo de referência

    flash(f"Produto '{produto_original.nome}' duplicado. Revise antes de salvar.", "info")

    # Redireciona para o form de criação com dados pré-preenchidos
    # passando via sessão (Flask) ou querystring se preferir.
    # Aqui, vamos usar o método via querystring para simplicidade:
    return redirect(
        url_for("produtos.gerenciar_produto", duplicar_de=produto_id)
    )



# ======================
# BAIXAR EXEMPLO CSV
# ======================
@produtos_bp.route("/exemplo_csv")
@login_required
def exemplo_csv():
    exemplo = io.StringIO()
    exemplo.write("sku,nome,preco_fornecedor,desconto_fornecedor,margem,ipi,ipi_tipo,difal,imposto_venda\n")
    exemplo.write("ABC123,Exemplo de Produto,3500,5,25,0,%_dentro,5,8\n")
    exemplo.seek(0)

    return send_file(
        io.BytesIO(exemplo.getvalue().encode("utf-8")),
        as_attachment=True,
        download_name="modelo_produtos.csv",
        mimetype="text/csv"
    )


# ======================
# API — TEXTO PARA WHATSAPP
# ======================
@produtos_bp.route("/api/produto/<int:produto_id>/whatsapp")
@login_required
def produto_whatsapp(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    produto.calcular_precos()

    texto = (
        f"*{produto.nome}*\n"
        f"💰 À vista: R$ {produto.preco_a_vista:,.2f}\n"
        f"📦 Custo total: R$ {produto.custo_total:,.2f}\n"
        f"💸 Lucro líquido: R$ {produto.lucro_liquido_real:,.2f}\n"
        f"🧮 Margem: {produto.margem or 0}%\n\n"
        f"Código: {produto.codigo}"
    )

    return jsonify({"texto_completo": texto})
