# ======================
# ROTAS — PRODUTOS (Unificado Fase 4B)
# ======================

from flask import (
    render_template, request, redirect, url_for, flash,
    jsonify, current_app, send_file
)
from flask_login import login_required
from werkzeug.utils import secure_filename
from app import db
from app.produtos import produtos_bp
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto
)
from decimal import Decimal, InvalidOperation
import io


# ======================
# LISTAGEM DE PRODUTOS — Sprint 4B
# ======================
@produtos_bp.route("/", endpoint="index")
@login_required
def index():
    """Listagem com filtros dinâmicos, busca por nome/código e ordenação."""
    termo = request.args.get("termo", "").strip()
    tipo = request.args.get("tipo", type=int)
    categoria = request.args.get("categoria", type=int)
    marca = request.args.get("marca", type=int)
    calibre = request.args.get("calibre", type=int)
    ordenar = request.args.get("ordenar", "nome_asc")

    query = Produto.query

    # 🔍 Busca inteligente (nome ou código)
    if termo:
        query = query.filter(
            db.or_(
                Produto.nome.ilike(f"%{termo}%"),
                Produto.codigo.ilike(f"%{termo}%")
            )
        )

    # 🎯 Filtros opcionais
    if tipo:
        query = query.filter(Produto.tipo_id == tipo)
    if categoria:
        query = query.filter(Produto.categoria_id == categoria)
    if marca:
        query = query.filter(Produto.marca_id == marca)
    if calibre:
        query = query.filter(Produto.calibre_id == calibre)

    # ↕️ Ordenação dinâmica
    ordem_map = {
        "nome_asc": Produto.nome.asc(),
        "nome_desc": Produto.nome.desc(),
        "preco_asc": Produto.preco_a_vista.asc(),
        "preco_desc": Produto.preco_a_vista.desc(),
        "lucro_asc": Produto.lucro_liquido_real.asc(),
        "lucro_desc": Produto.lucro_liquido_real.desc(),
        "atualizado_em_desc": Produto.atualizado_em.desc(),
    }
    query = query.order_by(ordem_map.get(ordenar, Produto.nome.asc()))

    produtos = query.all()

    # 🔄 Listas dinâmicas (para selects de filtro)
    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()

    return render_template(
        "produtos/index.html",
        produtos=produtos,
        tipos=tipos,
        categorias=categorias,
        marcas=marcas,
        calibres=calibres,
    )


# ======================
# CADASTRAR / EDITAR PRODUTO
# ======================
@produtos_bp.route("/novo", methods=["GET", "POST"])
@produtos_bp.route("/<int:produto_id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_produto(produto_id=None):
    """Cria ou edita um produto com relacionamentos de tipo/marca/calibre/funcionamento."""

    # 🔁 DUPLICAR PRODUTO
    duplicar_de = request.args.get("duplicar_de", type=int)
    if duplicar_de:
        produto_ref = Produto.query.get(duplicar_de)
        if produto_ref:
            produto = Produto(
                nome=produto_ref.nome,
                descricao=produto_ref.descricao,
                categoria_id=produto_ref.categoria_id,
                tipo_id=produto_ref.tipo_id,
                marca_id=produto_ref.marca_id,
                calibre_id=produto_ref.calibre_id,
                funcionamento_id=produto_ref.funcionamento_id,
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
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()
    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    funcionamentos = FuncionamentoProduto.query.order_by(FuncionamentoProduto.nome.asc()).all()

    if request.method == "POST":
        data = request.form
        codigo = (data.get("codigo") or "").strip().upper()
        nome = (data.get("nome") or "").strip()
        descricao = (data.get("descricao") or "").strip() or None

        def to_int(value):
            try:
                return int(value) if value else None
            except ValueError:
                return None

        produto.categoria_id = to_int(data.get("categoria_id"))
        produto.marca_id = to_int(data.get("marca_id"))
        produto.calibre_id = to_int(data.get("calibre_id"))
        produto.tipo_id = to_int(data.get("tipo_id"))
        produto.funcionamento_id = to_int(data.get("funcionamento_id"))

        existente = (
            Produto.query.filter(Produto.codigo == codigo)
            .filter(Produto.id != produto.id if produto.id else True)
            .first()
        )
        if existente:
            flash(f"⚠️ Já existe um produto com o código {codigo}.", "warning")
            return redirect(url_for("produtos.gerenciar_produto", produto_id=produto.id))

        produto.codigo = codigo
        produto.nome = nome
        produto.descricao = descricao

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

    return render_template(
        "produtos/form/produto_form.html",
        produto=produto,
        categorias=categorias,
        marcas=marcas,
        calibres=calibres,
        tipos=tipos,
        funcionamentos=funcionamentos,
    )


# ======================
# IMPORTAR PRODUTOS VIA PLANILHA
# ======================
@produtos_bp.route("/importar", methods=["GET", "POST"])
@login_required
def importar_produtos():
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if not arquivo:
            flash("Nenhum arquivo selecionado.", "warning")
            return redirect(url_for("produtos.importar_produtos"))

        try:
            from app.services.importacao import importar_produtos_planilha
            qtd, erros = importar_produtos_planilha(arquivo)
            flash(f"✅ {qtd} produtos importados com sucesso!", "success")
            if erros:
                flash(f"⚠️ Alguns produtos apresentaram erros: {', '.join(erros)}", "warning")
        except Exception as e:
            current_app.logger.error(f"Erro ao importar produtos: {e}")
            flash("❌ Erro ao processar a planilha de produtos.", "danger")

        return redirect(url_for("produtos.index"))

    return render_template("produtos/importar.html")


# ======================
# EXCLUIR PRODUTO
# ======================
@produtos_bp.route("/<int:produto_id>/excluir", methods=["POST"])
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
# BAIXAR EXEMPLO CSV
# ======================
@produtos_bp.route("/exemplo_csv")
@login_required
def exemplo_csv():
    exemplo = io.StringIO()
    exemplo.write("codigo,nome,tipo,marca,calibre,preco_fornecedor,desconto_fornecedor,margem,ipi,ipi_tipo,difal,imposto_venda\n")
    exemplo.write("ABC123,Exemplo de Produto,Arma de Fogo,Taurus,9mm,3500,5,25,0,%_dentro,5,8\n")
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
    if hasattr(produto, "calcular_precos"):
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

# ======================================================
# AUTO-SAVE - Atualiza produto parcialmente via AJAX + Histórico
# ======================================================
@produtos_bp.route("/auto-save/<int:produto_id>", methods=["POST"])
@login_required
def auto_save(produto_id):
    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({"success": False, "error": "Produto não encontrado"}), 404

    data = request.form
    alteracoes = []

    try:
        for field, value in data.items():
            if not hasattr(produto, field):
                continue

            valor_atual = getattr(produto, field)
            novo_valor = value or None

            # compara valores antes de salvar
            if str(valor_atual) != str(novo_valor):
                alteracoes.append({
                    "campo": field,
                    "valor_antigo": valor_atual,
                    "valor_novo": novo_valor
                })
                setattr(produto, field, novo_valor)

        # Só registra histórico se houver alterações
        if alteracoes:
            for alt in alteracoes:
                hist = ProdutoHistorico(
                    produto_id=produto.id,
                    campo=alt["campo"],
                    valor_antigo=str(alt["valor_antigo"]),
                    valor_novo=str(alt["valor_novo"]),
                    usuario_id=current_user.id,
                    usuario_nome=current_user.nome if hasattr(current_user, "nome") else current_user.email
                )
                db.session.add(hist)

        produto.atualizado_em = datetime.utcnow()
        db.session.commit()

        return jsonify({"success": True, "id": produto.id, "alteracoes": len(alteracoes)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ======================================================
# MODELO: HISTÓRICO DE ALTERAÇÕES DE PRODUTO
# ======================================================
from app import db
from datetime import datetime
from flask_login import current_user

class ProdutoHistorico(db.Model):
    __tablename__ = "produto_historico"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    campo = db.Column(db.String(100), nullable=False)
    valor_antigo = db.Column(db.Text)
    valor_novo = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    usuario_nome = db.Column(db.String(120))
    data_modificacao = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship("Produto", backref=db.backref("historicos", lazy=True))

    def __repr__(self):
        return f"<Histórico Produto {self.produto_id} ({self.campo})>"
