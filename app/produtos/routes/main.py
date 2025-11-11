from flask import render_template, request, redirect, url_for, flash, current_app, make_response
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, text
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import pytz
import time

from app import db
from .. import produtos_bp
from app.produtos.models import Produto, ProdutoHistorico
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto
)

# ============================================================
#  Cache leve em memória para fragmentos da listagem (AJAX)
#  - Apenas para listagem SEM filtros (home de produtos)
#  - TTL curto para não "congelar" preços/estoque
# ============================================================
_LIST_CACHE = {}  # key -> (expires_epoch, html)
_LIST_CACHE_TTL = 60  # segundos


def _cache_key_for_list(page: int, per_page: int, ordenar: str) -> str:
    return f"nofilter:p={page}:pp={per_page}:ord={ordenar}"


def _get_cached_fragment(page: int, per_page: int, ordenar: str):
    key = _cache_key_for_list(page, per_page, ordenar)
    item = _LIST_CACHE.get(key)
    now = time.time()
    if item and item[0] > now:
        return item[1]
    if item:
        # expirado
        _LIST_CACHE.pop(key, None)
    return None


def _set_cached_fragment(page: int, per_page: int, ordenar: str, html: str):
    key = _cache_key_for_list(page, per_page, ordenar)
    _LIST_CACHE[key] = (time.time() + _LIST_CACHE_TTL, html)


# ============================================================
# LISTAGEM DE PRODUTOS — com filtros, busca, ordenação e paginação
# - compatível com resposta parcial (AJAX) para _lista.html
# - otimizações:
#   * validação/normalização de parâmetros
#   * consulta enxuta (sem joins desnecessários)
#   * cache leve do fragmento quando não há filtros
# ============================================================
@produtos_bp.route("/", endpoint="index")
@login_required
def index():
    # -----------------------------
    # 1) Parâmetros validados
    # -----------------------------
    raw_termo = (request.args.get("termo") or "").strip()
    termo = raw_termo if raw_termo else ""

    def _to_int(qs_name):
        try:
            v = request.args.get(qs_name, type=int)
            return v if v and v > 0 else None
        except Exception:
            return None

    tipo = _to_int("tipo")
    categoria = _to_int("categoria")
    marca = _to_int("marca")
    calibre = _to_int("calibre")

    ordenar = request.args.get("ordenar", "nome_asc")
    ordem_map = {
        "nome_asc": Produto.nome.asc(),
        "nome_desc": Produto.nome.desc(),
        "preco_asc": Produto.preco_a_vista.asc(),
        "preco_desc": Produto.preco_a_vista.desc(),
        "lucro_asc": Produto.lucro_liquido_real.asc(),
        "lucro_desc": Produto.lucro_liquido_real.desc(),
        "atualizado_em_desc": Produto.atualizado_em.desc(),
    }
    ordem = ordem_map.get(ordenar, Produto.nome.asc())

    # limites sensatos
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", 20, type=int) or 20
    if per_page < 10:
        per_page = 10
    if per_page > 100:
        per_page = 100

    # -----------------------------
    # 2) Montagem de consulta
    #    (sem joinedload — listagem não precisa)
    # -----------------------------
    query = Produto.query

    # 🔍 Busca por nome ou código (case-insensitive)
    if termo:
        like = f"%{termo}%"
        query = query.filter(or_(Produto.nome.ilike(like), Produto.codigo.ilike(like)))

    # 🎯 Filtros opcionais
    if tipo:
        query = query.filter(Produto.tipo_id == tipo)
    if categoria:
        query = query.filter(Produto.categoria_id == categoria)
    if marca:
        query = query.filter(Produto.marca_id == marca)
    if calibre:
        query = query.filter(Produto.calibre_id == calibre)

    # ↕️ Ordenação
    query = query.order_by(ordem)

    # -----------------------------
    # 3) Paginação
    # -----------------------------
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    produtos = pagination.items

    # -----------------------------
    # 4) Listas para filtros (mantidas completas)
    # -----------------------------
    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()

    # -----------------------------
    # 5) Resposta parcial (AJAX) com cache leve quando NÃO há filtros
    # -----------------------------
    wants_fragment = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    has_any_filter = any([
        bool(termo), bool(tipo), bool(categoria),
        bool(marca), bool(calibre)
    ])

    if wants_fragment:
        if not has_any_filter:
            cached = _get_cached_fragment(page, per_page, ordenar)
            if cached:
                # Garante que o fragmento seja retornado com cabeçalhos adequados
                resp = make_response(cached)
                resp.headers["Cache-Control"] = "no-store"
                return resp

        html = render_template(
            "produtos/_lista.html",
            produtos=produtos,
            pagination=pagination,
            per_page=per_page,
            request=request,
        )
        if not has_any_filter:
            _set_cached_fragment(page, per_page, ordenar, html)
        resp = make_response(html)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # -----------------------------
    # 6) Página completa
    # -----------------------------
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


# ============================================================
# CADASTRAR / EDITAR PRODUTO
# - Mantém lógica atual de auditoria e cálculo
# - joinedload apenas no histórico (uso no form)
# ============================================================
@produtos_bp.route("/novo", methods=["GET", "POST"])
@produtos_bp.route("/<int:produto_id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_produto(produto_id=None):
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
        foto_atual = getattr(produto, "foto_url", None)

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

        # Código único
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
        produto.foto_url = data.get("foto_url") or foto_atual

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
            # Recalcula se existir método
            if hasattr(produto, "calcular_precos"):
                produto.calcular_precos()

            db.session.add(produto)
            db.session.flush()  # garante produto.id

            # Auditoria
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
            # Invalida cache da listagem sem filtros (dados mudaram)
            _LIST_CACHE.clear()
            flash("✅ Produto salvo com sucesso!", "success")
            return redirect(url_for("produtos.index"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar produto: {e}")
            flash("❌ Ocorreu um erro ao salvar o produto.", "danger")

    # Conversão de timezone do campo atualizado_em (exibição amigável)
    if getattr(produto, "atualizado_em", None):
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


# ============================================================
# EXCLUIR PRODUTO
# - Mantém compatibilidade com chamada via fetch (AJAX)
# - Limpa cache da listagem sem filtros após exclusão
# ============================================================
@produtos_bp.route("/<int:produto_id>/excluir", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    try:
        db.session.delete(produto)
        db.session.commit()
        # Invalida cache, pois a listagem mudou
        _LIST_CACHE.clear()
        flash("🗑️ Produto excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir produto: {e}")
        flash("❌ Erro ao excluir produto.", "danger")
    return redirect(url_for("produtos.index"))
