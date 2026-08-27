#app/loja/routes.py

from flask import render_template, abort, request, url_for, send_from_directory, current_app, redirect, Response, make_response, flash, session, jsonify
from flask_login import login_required
from app.loja import loja_bp
from app import db
from app.loja.models_admin import Banner, PaginaInstitucional
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.models import Taxa, Configuracao
from app.utils.r2_helpers import gerar_link_r2
from app.utils.thumbnail_utils import get_thumb_url
from app.catalogo.image_url_helper import convert_resized_url
import app.utils.parcelamento as parcelamento_logic
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, subqueryload
import os
import re
from datetime import datetime
import pytz

# ============================================================
# INTERCEPTADOR DE SEO: REDIRECIONAMENTO 301 (MIGRAÇÃO DE DOMÍNIO)
# ============================================================
@loja_bp.before_request
def redirecionar_legado_para_subdominio():
    # Verifica se o ambiente atual configurado é o ADMIN
    # e se a requisição veio bater no domínio antigo (app.m4tatica.com.br)
    if os.getenv("M4_AMBIENTE", "ADMIN") == "ADMIN":
        host = request.host.lower()
        if "app.m4tatica.com.br" in host:
            # Captura o caminho atual (ex: /loja/categoria/pistola)
            caminho_atual = request.path
            
            # Remove o prefixo '/loja' se ele existir para casar com a raiz do novo subdomínio
            if caminho_atual.startswith('/loja'):
                caminho_novo = caminho_atual[5:] # Remove os primeiros 5 caracteres (/loja)
            else:
                caminho_novo = caminho_atual
                
            # Garante que não vai quebrar a barra inicial
            if not caminho_novo.startswith('/'):
                caminho_novo = '/' + caminho_novo
                
            # Captura os parâmetros de busca (?q=taurus&marca=1) para não quebrar os filtros
            parametros = request.query_string.decode('utf-8')
            url_final = f"https://loja.m4tatica.com.br{caminho_novo}"
            if parametros:
                url_final += f"?{parametros}"
                
            # Dispara o Redirecionamento 301 Permanente (Crítico para SEO)
            return redirect(url_final, code=301)

try:
    from flask_caching import Cache
    cache_enabled = True
    cache = Cache() 
    
    def init_cache(app):
        app.config.update({
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 300
        })
        cache.init_app(app)
except ImportError:
    cache_enabled = False
    class NoOpCache:
        def cached(self, *args, **kwargs):
            def decorator(f): return f
            return decorator
        def get(self, key): return None
        def set(self, key, value, timeout=None): pass
    cache = NoOpCache()
    init_cache = lambda app: None
    print("Flask-Caching não instalado. Performance reduzida.")

def limpar_caminho_r2(caminho):
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


def _limpar_foto_para_fallback(caminho):
    """Retorna uma URL original segura para a segunda tentativa do navegador."""
    if not caminho:
        return ""

    valor = str(caminho).strip().split("%23", 1)[0].split("#", 1)[0]
    if valor.startswith(("http://", "https://", "/", "data:image/")):
        return valor
    return ""


def normalizar_foto_loja(caminho):
    """Converte formatos antigos de foto em uma URL pública estável."""
    fallback = url_for("static", filename="img/sem-foto.jpg")
    if not caminho:
        return fallback

    valor = str(caminho).strip()
    if not valor:
        return fallback

    # Fragmentos como ``#arquivo.png`` são usados em uploads temporários e
    # nunca devem ser enviados ao CDN como parte da chave do objeto.
    valor = valor.split("%23", 1)[0].split("#", 1)[0]

    # Preserva recursos internos que já são URLs válidas da aplicação.
    if valor.startswith(("/static/", "/catalogo/image-proxy/", "data:image/")):
        return valor

    try:
        url_publica = gerar_link_r2(limpar_caminho_r2(valor))
        return url_publica or fallback
    except Exception as e:
        current_app.logger.warning("Não foi possível normalizar a foto %s: %s", valor, e)
        return fallback

# ============================================================
# CONTEXT PROCESSOR: DISPONIBILIZA CATEGORIAS EM TODA A LOJA
# ============================================================
@loja_bp.app_context_processor
def inject_loja_data():
    cache_key = 'loja_data_v3'
    cached_res = cache.get(cache_key)
    if cached_res:
        return cached_res

    try:
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
            loja['banner_despachante_link'] = None

        res = dict(categorias_menu=categorias_menu, loja=loja, paginas_rodape=paginas_rodape)
        cache.set(cache_key, res, timeout=3600)
        return res

    except Exception as e:
        print(f"Erro crítico no inject_loja_data: {e}")
        return dict(categorias_menu=[], loja={}, paginas_rodape=[])

@loja_bp.app_context_processor
def inject_thumb_helper():
    return dict(
        get_thumb_url=get_thumb_url,
        imagem_otimizada=convert_resized_url,
    )

# ============================================================
# VITRINE PRINCIPAL (CIRURGIA A LASER: OPTIMIZED GET_SMART_CAT)
# ============================================================
@loja_bp.route('/api/buscar-fuzzy')
@cache.cached(timeout=300, query_string=True)
def buscar_fuzzy():
    termo = request.args.get('q', '').strip()
    if not termo or len(termo) < 2:
        return jsonify([])

    def serializar(produtos):
        resultados = []
        for p in produtos:
            precos = p.calcular_precos()
            resultados.append({
                'id': p.id,
                'nome': p.nome_comercial or p.nome,
                'slug': p.slug,
                'preco': float(precos.get('preco_a_vista', 0)),
                'foto': convert_resized_url(normalizar_foto_loja(p.foto_url), 80) if p.foto_url else url_for('static', filename='img/sem-foto.jpg')
            })
        return resultados

    # Busca Fuzzy usando pg_trgm similarity
    # Priorizamos nome_comercial, nome e codigo
    try:
        # Usamos similarity() do PostgreSQL via func
        # Nota: pg_trgm deve estar ativo no banco (ver migration 20260802_fuzzy_search_trgm)
        sim_nome = func.similarity(Produto.nome, termo)
        sim_comercial = func.similarity(Produto.nome_comercial, termo)
        sim_codigo = func.similarity(Produto.codigo, termo)

        # Maior similaridade entre os campos
        max_sim = func.greatest(sim_nome, sim_comercial, sim_codigo)

        produtos = Produto.query.filter(
            Produto.visivel_loja == True,
            or_(
                Produto.nome.op('%')(termo), # Operador de similaridade trigrama
                Produto.nome_comercial.op('%')(termo),
                Produto.codigo.op('%')(termo)
            )
        ).order_by(max_sim.desc()).limit(10).all()

        return jsonify(serializar(produtos))
    except Exception as e:
        current_app.logger.error(f"Erro na busca fuzzy (pg_trgm indisponível?): {e}")

        # CRÍTICO: sem isso, a transação do Postgres fica "abortada" e TODA
        # query seguinte nessa mesma conexão falha também — inclusive de
        # outras rotas (ex.: comparador), até a conexão ser reciclada.
        db.session.rollback()

        # Fallback para busca simples se o pg_trgm falhar ou não estiver disponível
        busca_like = f"%{termo}%"
        try:
            produtos = Produto.query.filter(
                Produto.visivel_loja == True,
                or_(
                    Produto.nome.ilike(busca_like),
                    Produto.nome_comercial.ilike(busca_like),
                    Produto.codigo.ilike(busca_like)
                )
            ).limit(10).all()
            return jsonify(serializar(produtos))
        except Exception as e2:
            current_app.logger.error(f"Erro no fallback da busca: {e2}")
            db.session.rollback()
            return jsonify([])

def _index_cache_key():
    """Mantém cache por URL e identidade da sessão da loja.

    A home compartilha o template com o estado de login; sem essa variação,
    uma resposta anonimizada poderia ser servida a um cliente autenticado.
    """
    caminho = request.full_path.rstrip('?')
    cliente_id = session.get('loja_cliente_id') or 'anon'
    return f"loja:index:v10:{caminho}:cliente:{cliente_id}"


@loja_bp.route('/')
@cache.cached(timeout=60, make_cache_key=_index_cache_key)
def index():
    termo_busca = request.args.get('q', '').strip()
    from app.produtos.configs.models import MarcaProduto
    
    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    if termo_busca:
        busca_like = f"%{termo_busca}%"

        try:
            # Mesma lógica de similaridade usada no /api/buscar-fuzzy: sem isso,
            # esta página (resultado final da busca) nunca "perdoa" erros de
            # digitação, mesmo que o dropdown de sugestões funcione.
            sim_nome = func.similarity(Produto.nome, termo_busca)
            sim_marca = func.similarity(MarcaProduto.nome, termo_busca)
            max_sim = func.greatest(sim_nome, sim_marca)

            query = Produto.query.join(Produto.marca_rel).filter(
                Produto.visivel_loja == True
            ).filter(
                or_(
                    Produto.nome.ilike(busca_like),
                    Produto.codigo.ilike(busca_like),
                    MarcaProduto.nome.ilike(busca_like),
                    Produto.nome.op('%')(termo_busca),
                    MarcaProduto.nome.op('%')(termo_busca)
                )
            ).options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))

            pagination = query.order_by(max_sim.desc(), Produto.criado_em.desc()).paginate(
                page=request.args.get('page', 1, type=int),
                per_page=12
            )
        except Exception as e:
            current_app.logger.error(f"Erro na busca com pg_trgm na vitrine (fallback p/ ilike): {e}")
            db.session.rollback()

            query = Produto.query.join(Produto.marca_rel).filter(
                Produto.visivel_loja == True
            ).filter(
                or_(
                    Produto.nome.ilike(busca_like),
                    Produto.codigo.ilike(busca_like),
                    MarcaProduto.nome.ilike(busca_like)
                )
            ).options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))

            pagination = query.order_by(Produto.criado_em.desc()).paginate(
                page=request.args.get('page', 1, type=int),
                per_page=12
            )

        return render_template('loja/index.html', 
                               produtos=pagination.items, 
                               pagination=pagination, 
                               gerar_link=gerador_limpo, 
                               termo_busca=termo_busca)

    lancamentos = cache.get('lancamentos_home_v5')
    if lancamentos is None:
        lancamentos = Produto.query.filter_by(visivel_loja=True)\
            .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
            .order_by(Produto.criado_em.desc()).limit(4).all()
        cache.set('lancamentos_home_v5', lancamentos, timeout=300)

    prateleiras = cache.get('prateleiras_home_v9')
    if prateleiras is None:
        def get_smart_cat(termo, limite=4):
            # CIRURGIA A LASER: subqueryload resolve o Timeout empacotando os dados numa viagem só
            cats = CategoriaProduto.query.filter(
                or_(CategoriaProduto.slug.ilike(f"%{termo}%"), CategoriaProduto.nome.ilike(f"%{termo}%"))
            ).options(subqueryload(CategoriaProduto.subcategorias)).all()
            
            if not cats: return []
            
            ids_alvo = list(set(
                [cat.id for cat in cats] + [s.id for cat in cats for s in cat.subcategorias]
            ))
            
            resultado = Produto.query.filter(
                Produto.visivel_loja == True,
                Produto.categoria_id.in_(ids_alvo)
            ).options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
             .order_by(Produto.id.desc()).limit(limite).all()
             
            return resultado

        prateleiras = {
            "Pistolas":   get_smart_cat("pistola"),
            "Revólveres": get_smart_cat("revolver"),
            "Rifles":     get_smart_cat("rifle"),
            "Munições":   get_smart_cat("muni"),
        }
        cache.set('prateleiras_home_v9', prateleiras, timeout=300)

    banners = cache.get('banners_home_v2')
    if banners is None:
        banners = Banner.query.filter_by(ativo=True).order_by(Banner.ordem.asc()).all()
        cache.set('banners_home_v2', banners, timeout=300)

    marcas_home = cache.get('marcas_home_v2')
    if marcas_home is None:
        marcas_home = MarcaProduto.query.filter(MarcaProduto.logo_url != None).all()
        cache.set('marcas_home_v2', marcas_home, timeout=3600)

    return render_template('loja/index.html', 
                           lancamentos=lancamentos, 
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
    produto = Produto.query.filter_by(slug=slug, visivel_loja=True)\
        .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
        .first_or_404()
    
    precos_key = f'precos_v2_{produto.id}'
    opcoes_parcelamento_key = f'opcoes_parcelamento_v2_{produto.id}'

    precos = cache.get(precos_key)
    opcoes_parcelamento = cache.get(opcoes_parcelamento_key)

    if precos is None or opcoes_parcelamento is None:
        precos = produto.calcular_precos()
        valor_base = float(precos.get('preco_a_vista') or 0.0)
        taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
        opcoes_parcelamento = parcelamento_logic.gerar_linhas_parcelas(valor_base, taxas)
        cache.set(precos_key, precos, timeout=3600)
        cache.set(opcoes_parcelamento_key, opcoes_parcelamento, timeout=3600)
    
    parcela_12x = next((item for item in opcoes_parcelamento if item["rotulo"] == "12x"), None)
    
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

    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    return render_template('loja/produto_detalhe.html', 
                       produto=produto, 
                       precos=precos,
                       opcoes_parcelamento=opcoes_parcelamento,
                       parcela_12x=parcela_12x,
                       relacionados=relacionados,
                       gerar_link=gerador_limpo,
                       get_thumb_url=get_thumb_url,
                       title=f"{produto.nome} - M4 Tática")


# ============================================================
# PÁGINA DE CATEGORIA
# ============================================================
@loja_bp.route('/categoria/<string:slug_categoria>')
@cache.cached(timeout=300, make_cache_key=lambda *args, **kwargs: request.full_path)
def categoria(slug_categoria):
    categoria_obj = CategoriaProduto.query.filter_by(slug=slug_categoria)\
        .options(subqueryload(CategoriaProduto.subcategorias)).first_or_404()
    
    marca_id = request.args.get('marca', type=int)
    calibre_id = request.args.get('calibre', type=int)
    preco_max = request.args.get('preco_max', type=float)
    sort = request.args.get('sort', 'novidades') 
    page = request.args.get('page', 1, type=int)
    
    cat_ids = [categoria_obj.id] + [sub.id for sub in categoria_obj.subcategorias]
    
    query = Produto.query.filter(Produto.categoria_id.in_(cat_ids), Produto.visivel_loja == True)\
                         .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))

    if marca_id: query = query.filter(Produto.marca_id == marca_id)
    if calibre_id: query = query.filter(Produto.calibre_id == calibre_id)
    if preco_max: query = query.filter(Produto.preco_a_vista <= preco_max)

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

    from app.produtos.configs.models import MarcaProduto, CalibreProduto
    
    marcas_vivas_key = f'marcas_sidebar_{categoria_obj.id}'
    calibres_vivas_key = f'calibres_sidebar_{categoria_obj.id}'
    
    marcas_vivas = cache.get(marcas_vivas_key)
    calibres_vivos = cache.get(calibres_vivas_key)

    if not marcas_vivas:
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
@cache.cached(timeout=3600)
def fale_conosco():
    return render_template('loja/fale_conosco.html', title="Fale Conosco - M4 Tática")

@loja_bp.route('/google8fe23db2fb19380f.html')
def google_verification():
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'google8fe23db2fb19380f.html')

@loja_bp.route('/sitemap.xml', strict_slashes=False)
@cache.cached(timeout=86400, key_prefix='sitemap_xml_v3')
def sitemap():
    # 1. Configuração do fuso horário e domínio base blindado contra o proxy do Render
    tz = pytz.timezone('America/Sao_Paulo')
    hoje = datetime.now(tz).strftime('%Y-%m-%d')
    base_url = "https://loja.m4tatica.com.br"
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # 2. Rota Principal (Home)
    xml.append(f'  <url>\n    <loc>{base_url}/</loc>\n    <lastmod>{hoje}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>')
    
    # 3. Rotas de Categorias
    categorias = CategoriaProduto.query.with_entities(CategoriaProduto.slug).all()
    for cat in categorias:
        xml.append(f'  <url>\n    <loc>{base_url}/categoria/{cat.slug}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>')
        
    # 4. Rotas de Produtos
    produtos = Produto.query.filter_by(visivel_loja=True).with_entities(Produto.slug).all()
    for prod in produtos:
        xml.append(f'  <url>\n    <loc>{base_url}/produto/{prod.slug}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>\n  </url>')
        
    xml.append('</urlset>')
    
    # 5. Gera a resposta forçando o cabeçalho correto para o Google ler como XML puro
    response = make_response('\n'.join(xml))
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response

@loja_bp.route('/robots.txt')
def robots_txt():
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'robots.txt')

@loja_bp.route('/sistema/otimizar-banco-m4')
@login_required
def otimizar_banco():
    from flask import current_app
    from sqlalchemy import text
    from app import db

    comandos = [
        "CREATE INDEX IF NOT EXISTS idx_produto_categoria ON produtos (categoria_id);",
        "CREATE INDEX IF NOT EXISTS idx_produto_marca ON produtos (marca_id);",
        "CREATE INDEX IF NOT EXISTS idx_produto_calibre ON produtos (calibre_id);",
        "CREATE INDEX IF NOT EXISTS idx_produto_slug ON produtos (slug);",
        "CREATE INDEX IF NOT EXISTS idx_produto_preco ON produtos (preco_a_vista);",
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

@loja_bp.route('/sistema/limpar-cache')
@login_required
def limpar_cache():
    try:
        cache.delete('prateleiras_home_v6')
        cache.delete('prateleiras_home_v7')
        cache.delete('prateleiras_home_v8')
        cache.delete('lancamentos_home_v4')
        cache.delete('destaques_home_v4')
        cache.delete('banners_home')
        cache.delete('marcas_home')
        cache.delete('loja_data_v3')
        return "✅ Cache limpo com sucesso! As prateleiras serão reconstruídas no próximo acesso."
    except Exception as e:
        return f"❌ Erro ao limpar cache: {str(e)}"

@loja_bp.route('/comparador')
def comparador():
    return render_template('loja/comparador.html')

@loja_bp.route('/api/produtos/buscar', methods=['GET'])
def buscar_produtos():
    termo = request.args.get('q', '').strip()
    if len(termo) < 2: return jsonify({'produtos': []})
    filtro = f"%{termo}%"

    from sqlalchemy import and_, or_
    from app.produtos.categorias.models import CategoriaProduto

    condicao_arma = and_(
        or_(
            Produto.funcionamento_id != None, 
            and_(Produto.requer_documentacao == True, Produto.calibre_id != None)
        ),
        ~Produto.categoria.has(CategoriaProduto.slug.ilike('%muni%')),
        ~Produto.categoria.has(CategoriaProduto.slug.ilike('%insumo%')),
        ~Produto.categoria.has(CategoriaProduto.slug.ilike('%carregador%'))
    )

    try:
        produtos = Produto.query.filter(
            condicao_arma,
            Produto.visivel_loja == True,
            or_(
                Produto.nome.ilike(filtro),
                Produto.nome_comercial.ilike(filtro),
                Produto.codigo.ilike(filtro)
            )
        ).limit(20).all()
    except Exception as e:
        # Defensivo: se a sessão do banco vier "envenenada" por uma
        # transação abortada em outra rota, isso evita um 500 aqui e
        # recupera a conexão para as próximas requisições.
        current_app.logger.error(f"Erro na busca do comparador: {e}")
        db.session.rollback()
        return jsonify({'produtos': []})

    resultado = []
    for p in produtos:
        foto = normalizar_foto_loja(p.foto_url)
        resultado.append({
            'id': p.id,
            'nome': p.nome_comercial or p.nome,
            'codigo': p.codigo,
            'categoria': p.categoria.nome if p.categoria else 'N/A',
            'calibre': p.calibre_rel.nome if p.calibre_rel else 'N/A',
            'preco': float(p.preco_a_vista or 0),
            'foto': foto,
            'foto_fallback': _limpar_foto_para_fallback(p.foto_url)
        })
    return jsonify({'produtos': resultado})

@loja_bp.route('/api/comparar', methods=['POST'])
def comparar_produtos():
    try:
        data = request.get_json()
        produto_ids = data.get('produto_ids', [])
        
        if not produto_ids or len(produto_ids) < 2: return jsonify({'erro': 'Selecione pelo menos 2 produtos'}), 400
        if len(produto_ids) > 3: return jsonify({'erro': 'Máximo 3 produtos'}), 400
        
        produtos = Produto.query.filter(Produto.id.in_(produto_ids)).all()
        if len(produtos) != len(produto_ids): return jsonify({'erro': 'Produto não encontrado'}), 404
        
        produtos_data = [p.to_compare_dict() for p in produtos]
        for produto_data, produto in zip(produtos_data, produtos):
            produto_data['foto_url_fallback'] = _limpar_foto_para_fallback(produto.foto_url)
            produto_data['foto_url'] = normalizar_foto_loja(produto.foto_url)

        analise_ia = gerar_analise_comparativa(produtos_data)
        modelo_ia = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b') if os.getenv('GROQ_API_KEY') else 'análise local'
        
        return jsonify({
            'produtos': produtos_data,
            'analise_ia': analise_ia,
            'modelo_ia': modelo_ia
        })
    except Exception as e:
        current_app.logger.error(f'Erro no comparador: {str(e)}')
        db.session.rollback()
        return jsonify({'erro': f'Erro ao processar comparação: {str(e)}'}), 500

def _formatar_brl(valor):
    """Formata valores monetários no padrão brasileiro para o laudo."""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        numero = 0.0
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _valor_especificacao(produto, chave):
    especificacoes = produto.get('especificacoes') or {}
    valor = especificacoes.get(chave)
    return valor if valor and valor != 'N/A' else 'Não informado'


def gerar_analise_local(produtos_data):
    """Gera um parecer completo e legível quando a LLM não está disponível."""
    mais_barato = min(produtos_data, key=lambda x: x.get('preco_vista') or 0)
    mais_caro = max(produtos_data, key=lambda x: x.get('preco_vista') or 0)
    diferenca = max((mais_caro.get('preco_vista') or 0) - (mais_barato.get('preco_vista') or 0), 0)
    preco_caro = mais_caro.get('preco_vista') or 0
    economia_pct = (diferenca / preco_caro * 100) if preco_caro else 0

    linhas_tabela = [
        '| Armamento | Fabricante | Calibre | Tipo | Preço à vista |',
        '|---|---|---|---|---:|',
    ]
    for produto in produtos_data:
        linhas_tabela.append(
            f"| {produto.get('nome', 'Produto')} | "
            f"{_valor_especificacao(produto, 'marca')} | "
            f"{produto.get('calibre') or 'Não informado'} | "
            f"{_valor_especificacao(produto, 'tipo')} | "
            f"{_formatar_brl(produto.get('preco_vista'))} |"
        )

    linhas_tecnicas = []
    for produto in produtos_data:
        linhas_tecnicas.append(
            f"### {produto.get('nome', 'Produto')}\n"
            f"- **Ação/sistema:** {_valor_especificacao(produto, 'funcionamento')}\n"
            f"- **Peso:** {_valor_especificacao(produto, 'peso')}\n"
            f"- **Comprimento:** {_valor_especificacao(produto, 'comprimento')}\n"
            f"- **Leitura técnica:** equipamento da categoria **{produto.get('categoria') or 'não informada'}**, "
            f"em calibre **{produto.get('calibre') or 'não informado'}**, com preço à vista de "
            f"**{_formatar_brl(produto.get('preco_vista'))}**."
        )

    return "\n\n".join([
        '# Análise comparativa técnica',
        '> Parecer gerado com base exclusivamente nos dados cadastrados no catálogo.\n> Campos não informados não foram inferidos.',
        '## Resumo executivo',
        f"Entre os produtos comparados, **{mais_barato.get('nome', 'o produto de menor preço')}** apresenta o menor investimento inicial, "
        f"com valor de **{_formatar_brl(mais_barato.get('preco_vista'))}**. A diferença para o produto de maior preço é de "
        f"**{_formatar_brl(diferenca)}** ({economia_pct:.1f}%). O menor preço, isoladamente, não substitui a avaliação de calibre, "
        'configuração, documentação e finalidade legal de uso.',
        '## Comparação objetiva',
        '\n'.join(linhas_tabela),
        '## Leitura técnica dos produtos',
        '\n\n'.join(linhas_tecnicas),
        '## Custo-benefício',
        f"A opção de menor preço é **{mais_barato.get('nome', 'não informado')}**, da marca **{_valor_especificacao(mais_barato, 'marca')}**. "
        f"Em relação ao produto de maior preço, a economia nominal é de **{_formatar_brl(diferenca)}**. "
        'Essa conclusão é financeira e deve ser complementada pela conferência das especificações e da disponibilidade comercial.',
        '## Conclusão',
        'A escolha deve considerar o conjunto de especificações, a adequação ao perfil documentado do comprador, a disponibilidade e o atendimento à legislação vigente. Este parecer é informativo e não substitui orientação técnica, jurídica ou do fabricante.',
    ])

def normalizar_markdown_analise(texto):
    """Remove cercas de código e garante uma apresentação Markdown consistente."""
    if not texto:
        return ''

    texto = str(texto).strip()
    texto = re.sub(r'^```(?:markdown|md)?\s*', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s*```$', '', texto)
    if not re.search(r'(?m)^#{1,6}\s+', texto):
        texto = f"## Parecer técnico\n\n{texto}"
    return texto


def gerar_analise_comparativa(produtos_data):
    api_key = os.getenv('GROQ_API_KEY')
    model_name = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')

    if not api_key:
        return gerar_analise_local(produtos_data)

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        produtos_info = "\n\n".join([
            f"[ARMAMENTO: {p.get('nome', '').upper()}]\n"
            f"Categoria: {p.get('categoria') or 'Não informado'}\n"
            f"Calibre: {p.get('calibre') or 'Não informado'}\n"
            f"Preço à vista: {_formatar_brl(p.get('preco_vista'))}\n"
            f"Fabricante: {_valor_especificacao(p, 'marca')}\n"
            f"Tipo: {_valor_especificacao(p, 'tipo')}\n"
            f"Ação/sistema: {_valor_especificacao(p, 'funcionamento')}\n"
            f"Peso: {_valor_especificacao(p, 'peso')}\n"
            f"Comprimento: {_valor_especificacao(p, 'comprimento')}"
            for p in produtos_data
        ])

        prompt = f"""Produza um parecer comparativo técnico, aprofundado e objetivo sobre os armamentos abaixo.

DADOS CADASTRADOS:
{produtos_info}

REGRAS OBRIGATÓRIAS:
1. Responda exclusivamente em Markdown válido, sem cercas de código e sem emojis.
2. Use exatamente estas seções: `# Análise comparativa técnica`, `## Resumo executivo`, `## Comparação objetiva`, `## Avaliação técnica`, `## Custo-benefício` e `## Conclusão`.
3. Inclua uma tabela Markdown comparando fabricante, calibre, tipo, ação/sistema, peso, comprimento e preço.
4. Não invente especificações, capacidades, dimensões ou desempenho. Quando um dado não estiver informado, escreva `Não informado`.
5. Diferencie claramente fatos presentes no cadastro de observações qualitativas. Não faça promessa de desempenho.
6. Compare os produtos individualmente e depois apresente um veredito equilibrado. O texto deve ter entre 550 e 750 palavras, em PT-BR formal.
7. Considere apenas uso legal, documentação e orientação do fabricante; não forneça instruções de emprego operacional.
"""

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um redator técnico especializado em fichas comparativas de produtos controlados. Seja preciso, formal e transparente sobre dados ausentes.",
                },
                {"role": "user", "content": prompt},
            ],
            model=model_name,
            temperature=0.2,
            max_tokens=1800,
        )
        resposta = chat_completion.choices[0].message.content
        return normalizar_markdown_analise(resposta) or gerar_analise_local(produtos_data)
    except Exception as e:
        current_app.logger.warning("Falha na análise Groq; usando parecer local: %s", e)
        return gerar_analise_local(produtos_data)
