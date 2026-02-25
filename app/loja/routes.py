from flask import render_template, abort, request, url_for, send_from_directory, current_app, redirect, Response, make_response
from app.loja import loja_bp
from app.loja.models_admin import Banner, PaginaInstitucional
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.models import Taxa, Configuracao
from app.utils.r2_helpers import gerar_link_r2
import app.utils.parcelamento as parcelamento_logic
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, subqueryload
import os

# --- AJUSTE PARA O RENDER ---
try:
    from flask_caching import Cache
    cache_enabled = True
    # Criamos o objeto cache aqui para que ele possa ser importado no __init__.py
    cache = Cache() 
    
    def init_cache(app):
        # A configuração de fato ocorre aqui
        app.config.update({
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 300
        })
        cache.init_app(app)
except ImportError:
    cache_enabled = False
    class NoOpCache:
        def cached(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
        def get(self, key):
            return None
        def set(self, key, value, timeout=None):
            pass
    cache = NoOpCache()
    init_cache = lambda app: None
    print("Flask-Caching não instalado. Performance reduzida.")

def limpar_caminho_r2(caminho):
    """
    Remove duplicidade do nome do bucket e barras extras no caminho.
    Lida com URLs completas ou caminhos internos do banco.
    """
    if not caminho:
        return ""
    
    if caminho.startswith("http"):
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
    """Busca categorias PAI e configurações de forma otimizada com cache manual."""
    # Tentativa de recuperar do cache para evitar processamento em toda requisição
    cache_key = 'loja_data_v3'
    cached_res = cache.get(cache_key)
    if cached_res:
        return cached_res

    try:
        # subqueryload é muito mais performático para carregar listas de subcategorias
        categorias_menu = CategoriaProduto.query.filter_by(pai_id=None, exibir_no_menu=True)\
            .options(subqueryload(CategoriaProduto.subcategorias))\
            .order_by(CategoriaProduto.ordem_exibicao.asc()).all()
        
        paginas_rodape = PaginaInstitucional.query.filter_by(visivel_rodape=True).all()
        
        config_objs = Configuracao.query.filter(Configuracao.chave.like('loja_%')).all()
        loja = {c.chave: c.valor for c in config_objs}
        
        banner_url = loja.get('loja_banner_despachante_url')
        if banner_url:
            loja['banner_despachante_link'] = gerar_link_r2(limpar_caminho_r2(banner_url))
        else:
            loja['banner_despachante_link'] = url_for('static', filename='img/bg-despachante.jpg')

        res = dict(categorias_menu=categorias_menu, loja=loja, paginas_rodape=paginas_rodape)
        
        # Salva no cache por 1 hora (3600s)
        cache.set(cache_key, res, timeout=3600)
        return res

    except Exception as e:
        print(f"Erro crítico no inject_loja_data: {e}")
        return dict(categorias_menu=[], loja={}, paginas_rodape=[])

# ============================================================
# VITRINE PRINCIPAL
# ============================================================
@loja_bp.route('/')
@cache.cached(timeout=60, query_string=True, key_prefix='index_v6') # query_string=True resolve o travamento
def index():
    termo_busca = request.args.get('q', '').strip()
    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    # 1. CASO DE BUSCA
    if termo_busca:
        busca_like = f"%{termo_busca}%"
        query = Produto.query.filter_by(visivel_loja=True).filter(
            or_(Produto.nome.ilike(busca_like), Produto.codigo.ilike(busca_like))
        ).options(joinedload(Produto.marca_rel), joinedload(Produto.categoria)) # Proteção na busca
        pagination = query.order_by(Produto.criado_em.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=12)
        return render_template('loja/index.html', 
                               produtos=pagination.items, 
                               pagination=pagination, 
                               gerar_link=gerador_limpo, 
                               termo_busca=termo_busca)

    # 2. LANÇAMENTOS E DESTAQUES (Joinedload para Marca E Categoria)
    lancamentos = cache.get('lancamentos_home_v4')
    if lancamentos is None:
        lancamentos = Produto.query.filter_by(visivel_loja=True)\
            .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
            .order_by(Produto.criado_em.desc()).limit(4).all()
        cache.set('lancamentos_home_v4', lancamentos, timeout=300)

    destaques = cache.get('destaques_home_v4')
    if destaques is None:
        destaques = Produto.query.filter_by(visivel_loja=True)\
            .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
            .order_by(func.random()).limit(4).all()
        cache.set('destaques_home_v4', destaques, timeout=300)

# 3. PRATELEIRAS INTELIGENTES (v5 - Correção da abrangência de Munições)
    prateleiras = cache.get('prateleiras_home_v5')
    if prateleiras is None:
        def get_smart_cat(termo):
            # Busca a categoria pai pelo nome ou slug
            cat = CategoriaProduto.query.filter(
                or_(CategoriaProduto.slug.ilike(f"%{termo}%"), CategoriaProduto.nome.ilike(f"%{termo}%"))
            ).first()
            if not cat: return []
            
            # Pega o ID da categoria pai + IDs de TODAS as subcategorias filhas
            ids_alvo = [cat.id]
            if cat.subcategorias:
                ids_alvo.extend([s.id for s in cat.subcategorias])
            
            # Busca produtos que estejam em qualquer um desses IDs
            return Produto.query.filter(Produto.visivel_loja == True, Produto.categoria_id.in_(ids_alvo))\
                          .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
                          .order_by(Produto.criado_em.desc()).limit(4).all()
        
        prateleiras = {
            "Pistolas": get_smart_cat("pistola"),
            "Rifles": get_smart_cat("rifle"),
            "Munições": get_smart_cat("muni") # Agora pegará Cal. 12, 9mm, .380, etc.
        }
        cache.set('prateleiras_home_v5', prateleiras, timeout=300)
    
    banners = cache.get('banners_home')
    if banners is None:
        banners = Banner.query.filter_by(ativo=True).order_by(Banner.ordem.asc()).all()
        cache.set('banners_home', banners, timeout=300)

    from app.produtos.configs.models import MarcaProduto
    marcas_home = cache.get('marcas_home')
    if marcas_home is None:
        marcas_home = MarcaProduto.query.filter(MarcaProduto.logo_url != None).all()
        cache.set('marcas_home', marcas_home, timeout=3600)

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
@cache.cached(timeout=300, make_cache_key=lambda *args, **kwargs: request.path)
def detalhe_produto(slug):
    # OTIMIZAÇÃO: Eager loading da marca e categoria para o produto principal
    # Isso evita que o template dispare novas queries ao carregar a página
    produto = Produto.query.filter_by(slug=slug, visivel_loja=True)\
        .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
        .first_or_404()
    
    # Chaves de cache específicas por produto
    precos_key = f'precos_v2_{produto.id}'
    opcoes_parcelamento_key = f'opcoes_parcelamento_v2_{produto.id}'

    precos = cache.get(precos_key)
    opcoes_parcelamento = cache.get(opcoes_parcelamento_key)

    if precos is None or opcoes_parcelamento is None:
        precos = produto.calcular_precos()
        valor_base = float(precos.get('preco_a_vista') or 0.0)
        
        # OTIMIZAÇÃO: Busca taxas de parcelamento
        taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
        opcoes_parcelamento = parcelamento_logic.gerar_linhas_parcelas(valor_base, taxas)
        
        cache.set(precos_key, precos, timeout=3600)
        cache.set(opcoes_parcelamento_key, opcoes_parcelamento, timeout=3600)
    
    # Busca rápida da parcela de 12x para exibição em destaque
    parcela_12x = next((item for item in opcoes_parcelamento if item["rotulo"] == "12x"), None)
    
    # 3. PRODUTOS RELACIONADOS (Otimizado com v10 para garantir limpeza de cache)
    # A lentidão relatada ocorria aqui; agora usamos joinedload e filtros eficientes
    relacionados_key = f'relacionados_v10_{produto.categoria_id}' 
    relacionados = cache.get(relacionados_key)
    
    if relacionados is None:
        relacionados = Produto.query.filter(
            Produto.categoria_id == produto.categoria_id, 
            Produto.id != produto.id,
            Produto.visivel_loja == True
        ).options(
            joinedload(Produto.marca_rel), 
            joinedload(Produto.categoria)
        ).limit(4).all()
        cache.set(relacionados_key, relacionados, timeout=3600)

    # Lambda para gerar links do R2 limpos
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
@cache.cached(timeout=300, make_cache_key=lambda *args, **kwargs: request.full_path)
def categoria(slug_categoria):
    # 1. Busca categoria pai e já traz subcategorias via subqueryload (mais rápido)
    categoria_obj = CategoriaProduto.query.filter_by(slug=slug_categoria)\
        .options(subqueryload(CategoriaProduto.subcategorias)).first_or_404()
    
    marca_id = request.args.get('marca', type=int)
    calibre_id = request.args.get('calibre', type=int)
    preco_max = request.args.get('preco_max', type=float)
    sort = request.args.get('sort', 'novidades') 
    page = request.args.get('page', 1, type=int)
    
    cat_ids = [categoria_obj.id] + [sub.id for sub in categoria_obj.subcategorias]
    
    # 2. Query de produtos principal
    query = Produto.query.filter(Produto.categoria_id.in_(cat_ids), Produto.visivel_loja == True)\
                         .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))

    if marca_id: query = query.filter(Produto.marca_id == marca_id)
    if calibre_id: query = query.filter(Produto.calibre_id == calibre_id)
    if preco_max: query = query.filter(Produto.preco_a_vista <= preco_max)

    # Ordenação
    if sort == 'menor_preco':
        query = query.order_by(Produto.preco_a_vista.asc())
    elif sort == 'maior_preco':
        query = query.order_by(Produto.preco_a_vista.desc())
    else:
        query = query.order_by(Produto.criado_em.desc())

    try:
        pagination = query.paginate(page=page, per_page=12, error_out=False)
    except Exception:
        abort(404)

    # 3. FILTROS LATERAIS (Otimização para evitar Timeout)
    from app.produtos.configs.models import MarcaProduto, CalibreProduto
    
    # Cache manual dos filtros por categoria para não reprocessar na paginação
    marcas_vivas_key = f'marcas_sidebar_{categoria_obj.id}'
    calibres_vivas_key = f'calibres_sidebar_{categoria_obj.id}'
    
    marcas_vivas = cache.get(marcas_vivas_key)
    calibres_vivos = cache.get(calibres_vivas_key)

    if not marcas_vivas:
        # O uso de any() é infinitamente mais rápido que join().distinct() para filtros
        marcas_vivas = MarcaProduto.query.filter(
            MarcaProduto.produtos.any(Produto.categoria_id.in_(cat_ids))
        ).options(subqueryload(MarcaProduto.produtos)).all()
        cache.set(marcas_vivas_key, marcas_vivas, timeout=600)
    
    if not calibres_vivos:
        calibres_vivos = CalibreProduto.query.filter(
            CalibreProduto.produtos.any(Produto.categoria_id.in_(cat_ids))
        ).options(subqueryload(CalibreProduto.produtos)).all()
        cache.set(calibres_vivas_key, calibres_vivos, timeout=600)

    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    return render_template('loja/categoria.html', 
                           produtos=pagination.items, pagination=pagination,
                           categoria_ativa=categoria_obj, marcas=marcas_vivas, 
                           calibres=calibres_vivos, sort_atual=sort,
                           filtros={'marca': marca_id, 'calibre': calibre_id, 'preco_max': preco_max},
                           gerar_link=gerador_limpo)

@loja_bp.route('/p/<string:slug>')
@cache.cached(timeout=3600, make_cache_key=lambda *args, **kwargs: request.path)
def exibir_pagina(slug):
    pagina = PaginaInstitucional.query.filter_by(slug=slug).first_or_404()
    return render_template('loja/pagina_institucional.html', pagina=pagina)

@loja_bp.route('/fale-conosco')
@cache.cached(timeout=3600) # Adicione isso!
def fale_conosco():
    return render_template('loja/fale_conosco.html', title="Fale Conosco - M4 Tática")

@loja_bp.route('/google8fe23db2fb19380f.html')
def google_verification():
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'google8fe23db2fb19380f.html')

@loja_bp.route('/sitemap.xml')
@cache.cached(timeout=86400, key_prefix='sitemap_xml_v2')
def sitemap():
    pages = []
    pages.append({'loc': url_for('loja.index', _external=True)})
    
    categorias_slugs = CategoriaProduto.query.with_entities(CategoriaProduto.slug).all()
    for cat_slug in categorias_slugs:
        pages.append({'loc': url_for('loja.categoria', slug_categoria=cat_slug.slug, _external=True)})
        
    produtos_slugs = Produto.query.filter_by(visivel_loja=True).with_entities(Produto.slug).all()
    for prod_slug in produtos_slugs:
        pages.append({'loc': url_for('loja.detalhe_produto', slug=prod_slug.slug, _external=True)})

    from app.utils.datetime import now_local
    sitemap_xml = render_template('loja/sitemap.xml', pages=pages, now_local=now_local)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

@loja_bp.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'robots.txt')

@loja_bp.route('/sistema/otimizar-banco-m4')
def otimizar_banco():
    # Apenas para segurança, você pode verificar uma senha ou IP aqui
    from flask import current_app
    from sqlalchemy import text
    from app import db # Certifique-se de que o 'db' está acessível

    comandos = [
        # Índices na tabela de PRODUTOS (nome da tabela: produtos)
        "CREATE INDEX IF NOT EXISTS idx_produto_categoria ON produtos (categoria_id);",
        "CREATE INDEX IF NOT EXISTS idx_produto_marca ON produtos (marca_id);",
        "CREATE INDEX IF NOT EXISTS idx_produto_calibre ON produtos (calibre_id);",
        "CREATE INDEX IF NOT EXISTS idx_produto_slug ON produtos (slug);",
        "CREATE INDEX IF NOT EXISTS idx_produto_preco ON produtos (preco_a_vista);",

        # Índice na tabela de CATEGORIAS (O nome correto deve ser categoria_produto)
        "CREATE INDEX IF NOT EXISTS idx_categoria_slug ON categoria_produto (slug);"
    ]

    try:
        for sql in comandos:
            db.session.execute(text(sql))
        db.session.commit()
        return "🔥 Operação Tática Concluída: Índices criados com sucesso!"
    except Exception as e:
        db.session.rollback()
        return f"❌ Erro na operação: {str(e)}"
