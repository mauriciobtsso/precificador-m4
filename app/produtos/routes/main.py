from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import pytz

from app import db
from .. import produtos_bp
from app.produtos.models import Produto, ProdutoHistorico
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto
)


# ======================
# LISTAGEM DE PRODUTOS — Sprint 4B + Paginação M4
# ======================
@produtos_bp.route("/", endpoint="index")
@login_required
def index():
    """Listagem de produtos com filtros, busca, ordenação e paginação."""
    termo = request.args.get("termo", "").strip()
    tipo = request.args.get("tipo", type=int)
    categoria = request.args.get("categoria", type=int)
    marca = request.args.get("marca", type=int)
    calibre = request.args.get("calibre", type=int)
    ordenar = request.args.get("ordenar", "nome_asc")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Produto.query

    # 🔍 Busca inteligente (nome ou código)
    if termo:
        query = query.filter(
            or_(
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

    # 📄 Paginação (mantendo filtros)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    produtos = pagination.items

    # 🔄 Listas dinâmicas (para selects de filtro)
    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()

    return render_template(
        "produtos/index.html",
        produtos=produtos,
        pagination=pagination,
        tipos=tipos,
        categorias=categorias,
        marcas=marcas,
        calibres=calibres,
        per_page=per_page,
    )


# ======================
# CADASTRAR / EDITAR PRODUTO
# ======================
@produtos_bp.route("/novo", methods=["GET", "POST"])
@produtos_bp.route("/<int:produto_id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_produto(produto_id=None):
    """Cria ou edita um produto com relacionamentos e auditoria."""
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
        if produto_id:
            produto = (
                Produto.query.options(joinedload(Produto.historicos))
                .filter_by(id=produto_id)
                .first()
            )
        else:
            produto = Produto()

    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()
    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    funcionamentos = FuncionamentoProduto.query.order_by(FuncionamentoProduto.nome.asc()).all()

    if request.method == "POST":
        data = request.form
        foto_atual = produto.foto_url

        def to_int(value):
            try:
                return int(value) if value else None
            except ValueError:
                return None

        def to_decimal(value):
            try:
                return Decimal(str(value or 0).replace(",", "."))
            except InvalidOperation:
                return Decimal(0)

        campos_auditados = [
            "codigo", "nome", "descricao",
            "categoria_id", "marca_id", "calibre_id", "tipo_id", "funcionamento_id",
            "preco_fornecedor", "desconto_fornecedor", "frete",
            "margem", "lucro_alvo", "preco_final",
            "ipi", "ipi_tipo", "difal", "imposto_venda",
        ]
        antes = {c: getattr(produto, c, None) for c in campos_auditados}

        codigo = (data.get("codigo") or "").strip().upper()
        nome = (data.get("nome") or "").strip()
        descricao = (data.get("descricao") or "").strip() or None

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
        produto.foto_url = data.get("foto_url") or produto.foto_url

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

        if not data.get("foto_url"):
            produto.foto_url = foto_atual

        try:
            if hasattr(produto, "calcular_precos"):
                produto.calcular_precos()

            db.session.add(produto)
            db.session.flush()

            registros = []

            if not produto_id:
                registros.append(ProdutoHistorico(
                    produto_id=produto.id,
                    campo="__acao__",
                    valor_antigo=None,
                    valor_novo="Criação de produto",
                    usuario_id=getattr(current_user, "id", None),
                    usuario_nome=getattr(current_user, "nome", None)
                    or getattr(current_user, "username", None)
                    or getattr(current_user, "email", None),
                    data_modificacao=datetime.utcnow(),
                ))

            campos_percentuais = ["ipi", "ipi_tipo", "difal", "imposto_venda"]

            def normalizar_valor(v, campo_nome):
                if v is None:
                    return None
                try:
                    v_float = float(v)
                    if campo_nome in campos_percentuais:
                        return f"{v_float:.2f} %"
                    return f"{v_float:.2f}"
                except (ValueError, TypeError):
                    return str(v)

            depois = {c: getattr(produto, c, None) for c in campos_auditados}
            for campo in campos_auditados:
                a, d = antes.get(campo), depois.get(campo)
                if str(a) != str(d):
                    registros.append(ProdutoHistorico(
                        produto_id=produto.id,
                        campo=campo,
                        valor_antigo=normalizar_valor(a, campo),
                        valor_novo=normalizar_valor(d, campo),
                        usuario_id=getattr(current_user, "id", None),
                        usuario_nome=getattr(current_user, "nome", None)
                        or getattr(current_user, "username", None)
                        or getattr(current_user, "email", None),
                        data_modificacao=datetime.utcnow(),
                    ))

            if registros:
                db.session.add_all(registros)

            db.session.commit()
            flash("✅ Produto salvo com sucesso!", "success")
            return redirect(url_for("produtos.index"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar produto: {e}")
            flash("❌ Ocorreu um erro ao salvar o produto.", "danger")

    if produto and produto.atualizado_em:
        try:
            fuso_fortaleza = pytz.timezone("America/Fortaleza")
            if produto.atualizado_em.tzinfo is None:
                produto.atualizado_em = produto.atualizado_em.replace(tzinfo=timezone.utc)
            produto.atualizado_em_local = produto.atualizado_em.astimezone(fuso_fortaleza)
        except Exception as e:
            current_app.logger.warning(f"Falha ao converter timezone: {e}")
            produto.atualizado_em_local = produto.atualizado_em

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
