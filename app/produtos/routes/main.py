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

from app.models import Taxa
import app.utils.parcelamento as parc
from app.utils.datetime import now_local 

from urllib.parse import urlparse
from app.produtos.routes.utils import _key_from_url

from app.utils.r2_helpers import gerar_link_r2

# ============================================================
#  Cache leve em memória para fragmentos da listagem (AJAX)
# ============================================================
_LIST_CACHE = {}  
_LIST_CACHE_TTL = 60 

def _cache_key_for_list(page: int, per_page: int, ordenar: str) -> str:
    return f"nofilter:p={page}:pp={per_page}:ord={ordenar}"

def _get_cached_fragment(page: int, per_page: int, ordenar: str):
    key = _cache_key_for_list(page, per_page, ordenar)
    item = _LIST_CACHE.get(key)
    now = time.time()
    if item and item[0] > now:
        return item[1]
    if item:
        _LIST_CACHE.pop(key, None)
    return None

def _set_cached_fragment(page: int, per_page: int, ordenar: str, html: str):
    key = _cache_key_for_list(page, per_page, ordenar)
    _LIST_CACHE[key] = (time.time() + _LIST_CACHE_TTL, html)

@produtos_bp.app_context_processor
def utility_processor():
    def gerar_link(path):
        if not path:
            return ""
        # Se já for uma URL completa, retorna ela mesma
        if path.startswith('http'):
            return path
        # Caso contrário, usa o helper do R2 para montar o link assinado ou público
        return gerar_link_r2(path)
    
    return dict(gerar_link=gerar_link)


# ============================================================
# LISTAGEM DE PRODUTOS
# ============================================================
@produtos_bp.route("/", endpoint="index")
@login_required
def index():
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

    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", 20, type=int) or 20
    if per_page < 10: per_page = 10
    if per_page > 100: per_page = 100

    query = Produto.query
    if termo:
        like = f"%{termo}%"
        query = query.filter(or_(Produto.nome.ilike(like), Produto.codigo.ilike(like)))

    if tipo: query = query.filter(Produto.tipo_id == tipo)
    if categoria: query = query.filter(Produto.categoria_id == categoria)
    if marca: query = query.filter(Produto.marca_id == marca)
    if calibre: query = query.filter(Produto.calibre_id == calibre)

    query = query.order_by(ordem)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    produtos = pagination.items

    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()

    wants_fragment = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    has_any_filter = any([bool(termo), bool(tipo), bool(categoria), bool(marca), bool(calibre)])

    agora = now_local()

    if wants_fragment:
        if not has_any_filter:
            cached = _get_cached_fragment(page, per_page, ordenar)
            if cached:
                resp = make_response(cached)
                resp.headers["Cache-Control"] = "no-store"
                return resp

        html = render_template("produtos/_lista.html", produtos=produtos, pagination=pagination, per_page=per_page, request=request, agora=agora)
        if not has_any_filter:
            _set_cached_fragment(page, per_page, ordenar, html)
        resp = make_response(html)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return render_template("produtos/index.html", produtos=produtos, pagination=pagination, tipos=tipos, categorias=categorias, marcas=marcas, calibres=calibres, per_page=per_page, agora=agora)


# ============================================================
# CADASTRAR / EDITAR PRODUTO (ATUALIZADO PARA E-COMMERCE)
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
                # Campos de E-commerce na duplicação
                requer_documentacao=produto_ref.requer_documentacao,
                visivel_loja=False # Sempre inicia invisível ao duplicar
            )
            flash(f"Produto '{produto_ref.nome}' duplicado. Revise antes de salvar.", "info")
        else:
            flash("⚠️ Produto de origem não encontrado para duplicação.", "warning")
            produto = Produto()
    else:
        if produto_id:
            produto = Produto.query.options(joinedload(Produto.historicos)).filter_by(id=produto_id).first()
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
            try: return int(value) if value else None
            except ValueError: return None

        def to_decimal(value):
            if not value: return Decimal(0)
            try:
                val_str = str(value).replace("R$", "").replace("%", "").strip()
                val_str = val_str.replace(",", ".") 
                return Decimal(val_str)
            except InvalidOperation:
                return Decimal(0)

        # Campos auditados incluindo os novos de e-commerce
        campos_auditados = [
            "codigo", "nome", "descricao",
            "categoria_id", "marca_id", "calibre_id", "tipo_id", "funcionamento_id",
            "preco_fornecedor", "desconto_fornecedor", "frete",
            "margem", "lucro_alvo", "preco_final",
            "ipi", "ipi_tipo", "difal", "imposto_venda",
            "promo_ativada", "promo_preco_fornecedor", "promo_data_inicio", "promo_data_fim",
            "visivel_loja", "requer_documentacao", "destaque_home", "eh_lancamento", "eh_outdoor"
        ]
        antes = {c: getattr(produto, c, None) for c in campos_auditados}

        codigo = (data.get("codigo") or "").strip().upper()
        nome = (data.get("nome") or "").strip()
        
        # Persistência básica
        produto.codigo = codigo
        produto.nome = nome
        produto.descricao = (data.get("descricao") or "").strip() or None
        produto.categoria_id = to_int(data.get("categoria_id"))
        produto.marca_id = to_int(data.get("marca_id"))
        produto.calibre_id = to_int(data.get("calibre_id"))
        produto.tipo_id = to_int(data.get("tipo_id"))
        produto.funcionamento_id = to_int(data.get("funcionamento_id"))
        produto.foto_url = data.get("foto_url") or foto_atual

        # Persistência Financeira
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

        # === NOVOS CAMPOS DE E-COMMERCE E CONTEÚDO WEB ===
        produto.visivel_loja = True if data.get("visivel_loja") == "on" else False
        produto.requer_documentacao = True if data.get("requer_documentacao") == "on" else False
        produto.destaque_home = True if data.get("destaque_home") == "on" else False
        produto.eh_lancamento = True if data.get("eh_lancamento") == "on" else False
        produto.eh_outdoor = True if data.get("eh_outdoor") == "on" else False
        
        produto.descricao_comercial = (data.get("descricao_comercial") or "").strip() or None
        produto.meta_title = (data.get("meta_title") or "").strip() or None
        produto.meta_description = (data.get("meta_description") or "").strip() or None

        # Promoção
        produto.promo_ativada = True if data.get("promo_ativada") == "on" else False
        produto.promo_preco_fornecedor = to_decimal(data.get("promo_preco_fornecedor"))
        
        p_inicio = data.get("promo_data_inicio")
        p_fim = data.get("promo_data_fim")
        if p_inicio:
            produto.promo_data_inicio = datetime.strptime(p_inicio, "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.timezone("America/Fortaleza"))
        else:
            produto.promo_data_inicio = None

        if p_fim:
            produto.promo_data_fim = datetime.strptime(p_fim, "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.timezone("America/Fortaleza"))
        else:
            produto.promo_data_fim = None

        try:
            if hasattr(produto, "calcular_precos"):
                produto.calcular_precos()

            db.session.add(produto)
            db.session.flush()

            # Auditoria
            registros = []
            if not produto_id:
                registros.append(ProdutoHistorico(
                    produto_id=produto.id,
                    campo="__acao__",
                    valor_novo="Criação de produto",
                    usuario_id=getattr(current_user, "id", None),
                    usuario_nome=getattr(current_user, "nome", None) or getattr(current_user, "username", None),
                    data_modificacao=datetime.utcnow(),
                ))

            depois = {c: getattr(produto, c, None) for c in campos_auditados}
            for campo in campos_auditados:
                a, d = antes.get(campo), depois.get(campo)
                if str(a) != str(d):
                    registros.append(ProdutoHistorico(
                        produto_id=produto.id,
                        campo=campo,
                        valor_antigo=str(a) if a is not None else None,
                        valor_novo=str(d) if d is not None else None,
                        usuario_id=getattr(current_user, "id", None),
                        usuario_nome=getattr(current_user, "nome", None) or getattr(current_user, "username", None),
                        data_modificacao=datetime.utcnow(),
                    ))

            if registros:
                db.session.add_all(registros)

            db.session.commit()
            _LIST_CACHE.clear()
            flash("✅ Produto salvo com sucesso!", "success")
            return redirect(url_for("produtos.index"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar produto: {e}")
            flash("❌ Ocorreu um erro ao salvar o produto.", "danger")

    # Tratamento de fuso para exibição
    if getattr(produto, "atualizado_em", None):
        try:
            fuso_fortaleza = pytz.timezone("America/Fortaleza")
            if produto.atualizado_em.tzinfo is None:
                produto.atualizado_em = produto.atualizado_em.replace(tzinfo=timezone.utc)
            produto.atualizado_em_local = produto.atualizado_em.astimezone(fuso_fortaleza)
        except Exception:
            produto.atualizado_em_local = produto.atualizado_em

    foto_proxy = None
    if produto and produto.foto_url:
        key = _key_from_url(produto.foto_url)
        foto_proxy = url_for('main.imagem_proxy', key=key) if key else produto.foto_url

    return render_template(
        "produtos/form/produto_form.html",
        produto=produto,
        foto_proxy=foto_proxy,
        categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos,
    )

# ============================================================
# EXCLUIR PRODUTO
# ============================================================
@produtos_bp.route("/<int:produto_id>/excluir", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    try:
        db.session.delete(produto)
        db.session.commit()
        _LIST_CACHE.clear()
        flash("🗑️ Produto excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir produto: {e}")
        flash("❌ Erro ao excluir produto.", "danger")
    return redirect(url_for("produtos.index"))

# ============================================================
# VISUALIZAR PRODUTO (AJAX)
# ============================================================
@produtos_bp.route("/<int:produto_id>/visualizar", methods=["GET"])
@login_required
def visualizar_produto(produto_id):
    produto = Produto.query.options(
        joinedload(Produto.categoria), joinedload(Produto.marca_rel),
        joinedload(Produto.calibre_rel), joinedload(Produto.tipo_rel),
        joinedload(Produto.funcionamento_rel)
    ).filter_by(id=produto_id).first_or_404()

    def currency(val):
        try: v = float(val or 0)
        except: v = 0.0
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    url_imagem = "/static/img/placeholder.jpg"
    if produto.foto_url:
        key = _key_from_url(produto.foto_url)
        if key: url_imagem = url_for('main.imagem_proxy', key=key)

    valor_base = float(produto.preco_final or produto.preco_a_vista or 0.0)
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    linhas_raw = parc.gerar_linhas_parcelas(valor_base, taxas)

    parcelas_fmt = []
    parcela_12x_val = None
    for l in linhas_raw:
        rot = l.get("rotulo") or ""
        parcela_val = l.get("parcela") or 0
        total_val = l.get("total") or 0
        parcelas_fmt.append({"rotulo": rot, "parcela": currency(parcela_val), "total": currency(total_val)})
        if rot == "12x": parcela_12x_val = parcela_val

    parcelado_label = f"12x de {currency(parcela_12x_val)}" if parcela_12x_val is not None else "-"

    return {
        "id": produto.id, "codigo": produto.codigo or "-", "nome": produto.nome, "descricao": produto.descricao or "",
        "foto_url": url_imagem,
        "categoria": produto.categoria.nome if produto.categoria else "-",
        "marca": produto.marca_rel.nome if produto.marca_rel else "-",
        "calibre": produto.calibre_rel.nome if produto.calibre_rel else "-",
        "tipo": produto.tipo_rel.nome if produto.tipo_rel else "-",
        "funcionamento": produto.funcionamento_rel.nome if produto.funcionamento_rel else "-",
        "preco_avista": currency(valor_base), "parcelado_label": parcelado_label, "parcelas": parcelas_fmt,
    }

