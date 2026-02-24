from flask import render_template, abort, request, url_for, send_from_directory, current_app, redirect, Response, make_response
from app.loja import loja_bp
from app.loja.models_admin import Banner, PaginaInstitucional
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.models import Taxa, Configuracao
from app.utils.r2_helpers import gerar_link_r2
import app.utils.parcelamento as parcelamento_logic
from sqlalchemy import or_, func
import os

def limpar_caminho_r2(caminho):
    """
    Remove duplicidade do nome do bucket e barras extras no caminho.
    Lida com URLs completas ou caminhos internos do banco.
    """
    if not caminho:
        return ""
    
    if caminho.startswith('http'):
        from urllib.parse import urlparse
        caminho = urlparse(caminho).path

    bucket_nome = "m4-clientes-docs"
    caminho_limpo = caminho.replace(f"/{bucket_nome}", "").replace(bucket_nome, "")
    caminho_limpo = caminho_limpo.replace("//", "/").lstrip("/")
    
    if "%23" in caminho_limpo:
        caminho_limpo = caminho_limpo.split("%23")[0]
    if "#" in caminho_limpo:
        caminho_limpo = caminho_limpo.split("#")[0]
        
    return caminho_limpo

# ============================================================
# CONTEXT PROCESSOR: DISPONIBILIZA CATEGORIAS EM TODA A LOJA
# ============================================================
@loja_bp.app_context_processor
def inject_loja_data():
    """Busca categorias PAI e configurações de forma otimizada."""
    try:
        # Carrega apenas categorias principais necessárias para o menu
        categorias_menu = CategoriaProduto.query.filter_by(pai_id=None, exibir_no_menu=True)\
            .order_by(CategoriaProduto.ordem_exibicao.asc()).all()
        
        paginas_rodape = PaginaInstitucional.query.filter_by(visivel_rodape=True).all()
        
        # OTIMIZAÇÃO: Busca todas as chaves da loja de uma vez
        config_objs = Configuracao.query.filter(Configuracao.chave.like('loja_%')).all()
        loja = {c.chave: c.valor for c in config_objs}
        
        # TRATAMENTO DO BANNER: Simplificado
        banner_url = loja.get('loja_banner_despachante_url')
        if banner_url:
            loja['banner_despachante_link'] = gerar_link_r2(limpar_caminho_r2(banner_url))
        else:
            loja['banner_despachante_link'] = url_for('static', filename='img/bg-despachante.jpg')

        return dict(categorias_menu=categorias_menu, loja=loja, paginas_rodape=paginas_rodape)
    except Exception as e:
        current_app.logger.error(f"Erro no inject_loja_data: {e}")
        return dict(categorias_menu=[], loja={}, paginas_rodape=[])

# ============================================================
# VITRINE PRINCIPAL
# ============================================================
@loja_bp.route('/')
def index():
    termo_busca = request.args.get('q', '').strip()
    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    # 1. CASO DE BUSCA
    if termo_busca:
        busca_like = f"%{termo_busca}%"
        query = Produto.query.filter_by(visivel_loja=True).filter(
            or_(Produto.nome.ilike(busca_like), Produto.codigo.ilike(busca_like))
        )
        pagination = query.order_by(Produto.criado_em.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=12)
        return render_template('loja/index.html', 
                               produtos=pagination.items, 
                               pagination=pagination, 
                               gerar_link=gerador_limpo, 
                               termo_busca=termo_busca)

    # 2. LANÇAMENTOS E DESTAQUES (Consultas rápidas e limitadas)
    lancamentos = Produto.query.filter_by(visivel_loja=True).order_by(Produto.criado_em.desc()).limit(4).all()
    destaques = Produto.query.filter_by(visivel_loja=True).order_by(func.random()).limit(4).all()

    # 3. PRATELEIRAS INTELIGENTES (Otimizadas para evitar N+1 queries)
    def get_smart_cat(termo):
        cat = CategoriaProduto.query.filter(
            or_(CategoriaProduto.slug.ilike(f"%{termo}%"), CategoriaProduto.nome.ilike(f"%{termo}%"))
        ).first()
        if not cat: return []
        ids = [cat.id] + [s.id for s in cat.subcategorias]
        return Produto.query.filter(Produto.visivel_loja==True, Produto.categoria_id.in_(ids))\
                      .order_by(Produto.criado_em.desc()).limit(4).all()

    prateleiras = {
        "Pistolas": get_smart_cat("pistola"),
        "Rifles": get_smart_cat("rifle"),
        "Munições": get_smart_cat("muni")
    }

    banners = Banner.query.filter_by(ativo=True).order_by(Banner.ordem.asc()).all()

    from app.produtos.configs.models import MarcaProduto
    marcas_home = MarcaProduto.query.filter(MarcaProduto.logo_url != None).all()

    return render_template('loja/index.html', 
                           lancamentos=lancamentos, 
                           destaques=destaques, 
                           prateleiras=prateleiras, 
                           banners=banners, 
                           marcas=marcas_home, 
                           gerar_link=gerador_limpo)

# ============================================================
# DETALHE DO PRODUTO
# ============================================================
@loja_bp.route('/produto/<string:slug>')
def detalhe_produto(slug):
    produto = Produto.query.filter_by(slug=slug, visivel_loja=True).first_or_404()
    precos = produto.calcular_precos()
    
    valor_base = float(precos.get('preco_a_vista') or 0.0)
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    opcoes_parcelamento = parcelamento_logic.gerar_linhas_parcelas(valor_base, taxas)
    
    parcela_12x = next((item for item in opcoes_parcelamento if item["rotulo"] == "12x"), None)
    
    # Busca relacionados da mesma categoria (Otimizado)
    relacionados = Produto.query.filter(
        Produto.categoria_id == produto.categoria_id, 
        Produto.id != produto.id,
        Produto.visivel_loja == True
    ).limit(4).all()

    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    return render_template('loja/produto_detalhe.html', 
                           produto=produto, 
                           precos=precos,
                           opcoes_parcelamento=opcoes_parcelamento,
                           parcela_12x=parcela_12x,
                           relacionados=relacionados,
                           gerar_link=gerador_limpo,
                           title=f"{produto.nome} - M4 Tática")

# ============================================================
# PÁGINA DE CATEGORIA
# ============================================================
@loja_bp.route('/categoria/<string:slug_categoria>')
def categoria(slug_categoria):
    categoria_obj = CategoriaProduto.query.filter_by(slug=slug_categoria).first_or_404()
    
    marca_id = request.args.get('marca', type=int)
    calibre_id = request.args.get('calibre', type=int)
    preco_max = request.args.get('preco_max', type=float)
    sort = request.args.get('sort', 'novidades') 
    page = request.args.get('page', 1, type=int)
    
    cat_ids = [categoria_obj.id] + [sub.id for sub in categoria_obj.subcategorias]
    query = Produto.query.filter(Produto.categoria_id.in_(cat_ids), Produto.visivel_loja == True)

    if marca_id: query = query.filter(Produto.marca_id == marca_id)
    if calibre_id: query = query.filter(Produto.calibre_id == calibre_id)
    if preco_max: query = query.filter(Produto.preco_a_vista <= preco_max)

    if sort == 'menor_preco':
        query = query.order_by(Produto.preco_a_vista.asc())
    elif sort == 'maior_preco':
        query = query.order_by(Produto.preco_a_vista.desc())
    else:
        query = query.order_by(Produto.criado_em.desc())

    pagination = query.paginate(page=page, per_page=12)

    from app.produtos.configs.models import MarcaProduto, CalibreProduto
    marcas_vivas = MarcaProduto.query.join(Produto).filter(Produto.categoria_id.in_(cat_ids)).distinct().all()
    calibres_vivos = CalibreProduto.query.join(Produto).filter(Produto.categoria_id.in_(cat_ids)).distinct().all()

    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    return render_template('loja/categoria.html', 
                           produtos=pagination.items, pagination=pagination,
                           categoria_ativa=categoria_obj, marcas=marcas_vivas, 
                           calibres=calibres_vivos, sort_atual=sort,
                           filtros={'marca': marca_id, 'calibre': calibre_id, 'preco_max': preco_max},
                           gerar_link=gerador_limpo)

@loja_bp.route('/p/<string:slug>')
def exibir_pagina(slug):
    pagina = PaginaInstitucional.query.filter_by(slug=slug).first_or_404()
    return render_template('loja/pagina_institucional.html', pagina=pagina)

@loja_bp.route('/fale-conosco')
def fale_conosco():
    return render_template('loja/fale_conosco.html', title="Fale Conosco - M4 Tática")

@loja_bp.route('/google8fe23db2fb19380f.html')
def google_verification():
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'google8fe23db2fb19380f.html')

@loja_bp.route('/sitemap.xml')
def sitemap():
    """Gera sitemap otimizado apenas com os slugs."""
    pages = []
    pages.append({'loc': url_for('loja.index', _external=True)})
    
    categorias = CategoriaProduto.query.with_entities(CategoriaProduto.slug).all()
    for cat in categorias:
        pages.append({'loc': url_for('loja.categoria', slug_categoria=cat.slug, _external=True)})
        
    produtos = Produto.query.filter_by(visivel_loja=True).with_entities(Produto.slug).all()
    for prod in produtos:
        pages.append({'loc': url_for('loja.detalhe_produto', slug=prod.slug, _external=True)})

    from app.utils.datetime import now_local
    sitemap_xml = render_template('loja/sitemap.xml', pages=pages, now_local=now_local)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

@loja_bp.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'robots.txt')