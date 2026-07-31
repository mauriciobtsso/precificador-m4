# app/catalogo/routes.py
# ============================================================
# CATÁLOGO DE ATENDIMENTO — M4 TÁTICA
# Interface presencial otimizada para iPad Mini A1454
# Reutiliza 100% dos models, queries e utilitários existentes
# ============================================================

import re
import unicodedata
from flask import render_template, request, jsonify, abort, current_app
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, subqueryload

from app.catalogo import catalogo_bp
from app import db
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import MarcaProduto, CalibreProduto
from app.models import Configuracao
from app.utils.r2_helpers import gerar_link_r2
from app.utils.thumbnail_utils import get_thumb_url

# ────────────────────────────────────────────────────────────
# HELPER LOCAL: compatível com o padrão de loja/routes.py
# ────────────────────────────────────────────────────────────
def _limpar_caminho_r2(caminho: str) -> str:
    """Extrai r2_key limpo — mesmo padrão de app/loja/routes.py."""
    if not caminho:
        return ""
    if caminho.startswith("http"):
        from urllib.parse import urlparse
        caminho = urlparse(caminho).path
    for bucket in ("m4-loja-publico", "m4-clientes-docs"):
        if caminho.lstrip("/").startswith(bucket + "/"):
            caminho = caminho.lstrip("/")[len(bucket) + 1:]
            break
    caminho = caminho.replace("//", "/").lstrip("/")
    return caminho.split("%23")[0].split("#")[0]


def _gerador_link(path: str) -> str:
    return gerar_link_r2(_limpar_caminho_r2(path))


# ────────────────────────────────────────────────────────────
# HELPER: normaliza termos de busca para tolerância a variações
# Ex: "9mm" == "9 MM" == "9-mm"
# ────────────────────────────────────────────────────────────
def _normalizar_termo(termo: str) -> str:
    """Remove acentos, converte para minúsculas, colapsa separadores."""
    termo = unicodedata.normalize('NFKD', termo).encode('ascii', 'ignore').decode('ascii')
    termo = termo.lower().strip()
    # Colapsa espaços, hífens, pontos, underscores em espaço único
    termo = re.sub(r'[\s\-_\.]+', ' ', termo)
    return termo


def _build_search_conditions(termo: str):
    """
    Monta condições OR tolerantes para busca.
    Gera múltiplos padrões ILIKE para cobrir variações do termo.
    """
    normalizado = _normalizar_termo(termo)
    # Gera variantes: com espaço, sem espaço, com hífen
    variantes = {normalizado}
    sem_espaco = normalizado.replace(' ', '')
    if sem_espaco != normalizado:
        variantes.add(sem_espaco)
    com_hifen = normalizado.replace(' ', '-')
    if com_hifen != normalizado:
        variantes.add(com_hifen)

    condicoes = []
    for v in variantes:
        filtro = f"%{v}%"
        condicoes.extend([
            Produto.nome.ilike(filtro),
            Produto.nome_comercial.ilike(filtro),
            Produto.codigo.ilike(filtro),
            Produto.descricao.ilike(filtro),
            Produto.tags_palavras_chave.ilike(filtro),
            Produto.descricao_comercial.ilike(filtro),
        ])

    # Busca também no termo original (com acentos, case-insensitive)
    filtro_original = f"%{termo}%"
    condicoes.extend([
        Produto.nome.ilike(filtro_original),
        Produto.nome_comercial.ilike(filtro_original),
        Produto.codigo.ilike(filtro_original),
        Produto.descricao.ilike(filtro_original),
        Produto.tags_palavras_chave.ilike(filtro_original),
    ])

    return condicoes


# ────────────────────────────────────────────────────────────
# CONTEXT PROCESSOR: dados comuns a todos os templates do catálogo
# ────────────────────────────────────────────────────────────
@catalogo_bp.context_processor
def inject_catalogo_data():
    """Injeta categorias e configurações globais no contexto do catálogo."""
    try:
        categorias = CategoriaProduto.query.filter_by(pai_id=None)\
            .options(subqueryload(CategoriaProduto.subcategorias))\
            .order_by(CategoriaProduto.ordem_exibicao.asc()).all()

        config_objs = Configuracao.query.filter(
            Configuracao.chave.like('loja_%')
        ).all()
        loja_config = {c.chave: c.valor for c in config_objs}

        return dict(
            catalogo_categorias=categorias,
            loja_config=loja_config,
            get_thumb_url=get_thumb_url,
            catalogo_gerar_link=_gerador_link,
        )
    except Exception as e:
        current_app.logger.error(f"[CATALOGO] Erro no context_processor: {e}")
        return dict(
            catalogo_categorias=[],
            loja_config={},
            get_thumb_url=get_thumb_url,
            catalogo_gerar_link=_gerador_link,
        )


# ============================================================
# ROTA: PÁGINA INICIAL DO CATÁLOGO
# ============================================================
@catalogo_bp.route('/', strict_slashes=False)
def index():
    """
    Página inicial do catálogo de atendimento.
    Exibe: campo de busca, categorias, destaques, lançamentos, promoções.
    """
    opts = (joinedload(Produto.marca_rel), joinedload(Produto.categoria))

    # Destaques (destaque_home=True)
    destaques = Produto.query\
        .filter_by(visivel_loja=True, destaque_home=True)\
        .options(*opts)\
        .order_by(Produto.criado_em.desc())\
        .limit(8).all()

    # Se não há destaques marcados, usa os mais recentes
    if not destaques:
        destaques = Produto.query\
            .filter_by(visivel_loja=True)\
            .options(*opts)\
            .order_by(Produto.criado_em.desc())\
            .limit(8).all()

    # Lançamentos (últimos cadastrados)
    lancamentos = Produto.query\
        .filter_by(visivel_loja=True)\
        .options(*opts)\
        .order_by(Produto.criado_em.desc())\
        .limit(8).all()

    # Promoções ativas
    from app.utils.datetime import now_local
    agora = now_local()
    promocoes = Produto.query.filter(
        Produto.visivel_loja == True,
        Produto.promo_ativada == True,
        Produto.promo_data_inicio <= agora,
        Produto.promo_data_fim >= agora,
    ).options(*opts).limit(8).all()

    return render_template(
        'catalogo/index.html',
        destaques=destaques,
        lancamentos=lancamentos,
        promocoes=promocoes,
        gerar_link=_gerador_link,
    )


# ============================================================
# ROTA: DETALHE DO PRODUTO
# ============================================================
@catalogo_bp.route('/produto/<string:slug>')
def produto(slug):
    """
    Página de detalhe do produto — interface de apresentação premium.
    Acessível também por ID: /catalogo/produto/<id> via redirecionamento.
    """
    p = Produto.query.filter_by(slug=slug, visivel_loja=True)\
        .options(
            joinedload(Produto.marca_rel),
            joinedload(Produto.categoria),
            joinedload(Produto.calibre_rel),
            joinedload(Produto.tipo_rel),
            joinedload(Produto.funcionamento_rel),
        ).first_or_404()

    # Produtos relacionados: mesma categoria E/OU mesmo calibre
    relacionados_query = Produto.query.filter(
        Produto.visivel_loja == True,
        Produto.id != p.id,
    ).options(
        joinedload(Produto.marca_rel),
        joinedload(Produto.categoria),
    )

    # Tenta por categoria + calibre primeiro
    if p.categoria_id and p.calibre_id:
        relacionados = relacionados_query.filter(
            or_(
                Produto.categoria_id == p.categoria_id,
                Produto.calibre_id == p.calibre_id,
            )
        ).limit(6).all()
    elif p.categoria_id:
        relacionados = relacionados_query.filter(
            Produto.categoria_id == p.categoria_id
        ).limit(6).all()
    elif p.calibre_id:
        relacionados = relacionados_query.filter(
            Produto.calibre_id == p.calibre_id
        ).limit(6).all()
    else:
        relacionados = relacionados_query.limit(6).all()

    # Preço de venda (público — mesmo da loja virtual)
    precos = p.calcular_precos()

    return render_template(
        'catalogo/produto.html',
        produto=p,
        precos=precos,
        relacionados=relacionados,
        gerar_link=_gerador_link,
    )


# ============================================================
# ROTA: ACESSO POR ID (redireciona para slug)
# ============================================================
@catalogo_bp.route('/produto/id/<int:produto_id>')
def produto_por_id(produto_id):
    """Redireciona acesso por ID para a URL canônica por slug."""
    from flask import redirect, url_for
    p = Produto.query.get_or_404(produto_id)
    if not p.visivel_loja:
        abort(404)
    return redirect(url_for('catalogo.produto', slug=p.slug), code=301)


# ============================================================
# API: BUSCA INSTANTÂNEA (JSON)
# ============================================================
@catalogo_bp.route('/api/buscar')
def api_buscar():
    """
    Endpoint de busca instantânea para o campo de pesquisa.
    Retorna JSON com até 20 produtos.
    Busca tolerante: normaliza acentuação, maiúsculas, separadores.
    Busca em: nome, nome_comercial, codigo, descricao, tags, calibre, marca, categoria.
    """
    termo = request.args.get('q', '').strip()

    if len(termo) < 2:
        return jsonify({'produtos': [], 'total': 0})

    try:
        condicoes = _build_search_conditions(termo)

        # Busca por calibre (JOIN)
        filtro_calibre = f"%{_normalizar_termo(termo)}%"
        filtro_calibre_orig = f"%{termo}%"

        produtos = Produto.query.outerjoin(Produto.calibre_rel)\
            .outerjoin(Produto.marca_rel)\
            .outerjoin(Produto.categoria)\
            .filter(
                Produto.visivel_loja == True,
                or_(
                    *condicoes,
                    CalibreProduto.nome.ilike(filtro_calibre_orig),
                    MarcaProduto.nome.ilike(filtro_calibre_orig),
                    CategoriaProduto.nome.ilike(filtro_calibre_orig),
                )
            ).options(
                joinedload(Produto.marca_rel),
                joinedload(Produto.categoria),
                joinedload(Produto.calibre_rel),
            ).order_by(
                Produto.destaque_home.desc(),
                Produto.criado_em.desc()
            ).limit(20).all()

        resultado = []
        for p in produtos:
            foto_url = p.foto_url or ''
            if foto_url and not foto_url.startswith('http'):
                foto_url = _gerador_link(foto_url)
            elif not foto_url:
                foto_url = '/static/img/placeholder.jpg'

            # Usa thumbnail para performance no autocomplete
            thumb = get_thumb_url(p.foto_url, 't160') if p.foto_url else foto_url

            resultado.append({
                'id': p.id,
                'slug': p.slug,
                'nome': p.nome_comercial or p.nome,
                'codigo': p.codigo,
                'categoria': p.categoria.nome if p.categoria else '',
                'calibre': p.calibre_rel.nome if p.calibre_rel else '',
                'marca': p.marca_rel.nome if p.marca_rel else '',
                'preco': float(p.preco_a_vista or 0),
                'foto': thumb,
                'disponivel': (p.estoque_disponivel or 0) > 0,
                'em_promocao': bool(p.promo_ativada),
            })

        return jsonify({'produtos': resultado, 'total': len(resultado)})

    except Exception as e:
        current_app.logger.error(f"[CATALOGO] Erro na busca: {e}")
        return jsonify({'produtos': [], 'total': 0, 'erro': 'Erro interno'}), 500


# ============================================================
# API: PRODUTOS RELACIONADOS (para carregamento lazy na página)
# ============================================================
@catalogo_bp.route('/api/produto/<int:produto_id>/relacionados')
def api_relacionados(produto_id):
    """Retorna JSON com produtos relacionados — categoria e/ou calibre."""
    try:
        p = Produto.query.get_or_404(produto_id)

        query = Produto.query.filter(
            Produto.visivel_loja == True,
            Produto.id != produto_id,
        ).options(
            joinedload(Produto.marca_rel),
            joinedload(Produto.categoria),
        )

        if p.categoria_id and p.calibre_id:
            query = query.filter(or_(
                Produto.categoria_id == p.categoria_id,
                Produto.calibre_id == p.calibre_id,
            ))
        elif p.categoria_id:
            query = query.filter(Produto.categoria_id == p.categoria_id)

        relacionados = query.limit(6).all()

        resultado = []
        for r in relacionados:
            thumb = get_thumb_url(r.foto_url, 't280') if r.foto_url else '/static/img/placeholder.jpg'
            resultado.append({
                'id': r.id,
                'slug': r.slug,
                'nome': r.nome_comercial or r.nome,
                'marca': r.marca_rel.nome if r.marca_rel else '',
                'categoria': r.categoria.nome if r.categoria else '',
                'preco': float(r.preco_a_vista or 0),
                'foto': thumb,
            })

        return jsonify({'relacionados': resultado})
    except Exception as e:
        current_app.logger.error(f"[CATALOGO] Erro em relacionados: {e}")
        return jsonify({'relacionados': []}), 500


# ============================================================
# API: CATEGORIAS COM CONTAGEM (para chips de filtro)
# ============================================================
@catalogo_bp.route('/api/categorias')
def api_categorias():
    """Retorna categorias com contagem de produtos visíveis."""
    try:
        categorias = CategoriaProduto.query\
            .options(subqueryload(CategoriaProduto.subcategorias))\
            .order_by(CategoriaProduto.ordem_exibicao.asc()).all()

        resultado = []
        for cat in categorias:
            # Conta produtos nesta categoria e subcategorias
            ids = [cat.id] + [s.id for s in cat.subcategorias]
            total = Produto.query.filter(
                Produto.categoria_id.in_(ids),
                Produto.visivel_loja == True,
            ).count()

            if total > 0:
                resultado.append({
                    'id': cat.id,
                    'nome': cat.nome,
                    'slug': cat.slug,
                    'icone': cat.icone_loja or '',
                    'total': total,
                })

        return jsonify({'categorias': resultado})
    except Exception as e:
        current_app.logger.error(f"[CATALOGO] Erro em categorias: {e}")
        return jsonify({'categorias': []}), 500


# ============================================================
# API: FILTRAR POR CATEGORIA
# ============================================================
@catalogo_bp.route('/api/categoria/<string:slug>')
def api_categoria(slug):
    """Retorna produtos de uma categoria para os filtros de chip."""
    try:
        cat = CategoriaProduto.query.filter_by(slug=slug)\
            .options(subqueryload(CategoriaProduto.subcategorias))\
            .first_or_404()

        ids = [cat.id] + [s.id for s in cat.subcategorias]
        page = request.args.get('page', 1, type=int)

        pagination = Produto.query.filter(
            Produto.categoria_id.in_(ids),
            Produto.visivel_loja == True,
        ).options(
            joinedload(Produto.marca_rel),
            joinedload(Produto.categoria),
            joinedload(Produto.calibre_rel),
        ).order_by(
            Produto.destaque_home.desc(),
            Produto.criado_em.desc()
        ).paginate(page=page, per_page=20, error_out=False)

        resultado = []
        for p in pagination.items:
            thumb = get_thumb_url(p.foto_url, 't280') if p.foto_url else '/static/img/placeholder.jpg'
            resultado.append({
                'id': p.id,
                'slug': p.slug,
                'nome': p.nome_comercial or p.nome,
                'marca': p.marca_rel.nome if p.marca_rel else '',
                'calibre': p.calibre_rel.nome if p.calibre_rel else '',
                'preco': float(p.preco_a_vista or 0),
                'foto': thumb,
                'disponivel': (p.estoque_disponivel or 0) > 0,
                'em_promocao': bool(p.promo_ativada),
            })

        return jsonify({
            'produtos': resultado,
            'total': pagination.total,
            'paginas': pagination.pages,
            'pagina_atual': page,
            'categoria': {'nome': cat.nome, 'slug': cat.slug},
        })
    except Exception as e:
        current_app.logger.error(f"[CATALOGO] Erro em categoria: {e}")
        return jsonify({'produtos': [], 'total': 0}), 500
