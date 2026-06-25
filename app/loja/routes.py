#app/loja/routes.py

from flask import render_template, abort, request, url_for, send_from_directory, current_app, redirect, Response, make_response, flash, session, jsonify
from app.loja import loja_bp
from app import db
from app.loja.models_admin import Banner, PaginaInstitucional
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.models import Taxa, Configuracao
from app.utils.r2_helpers import gerar_link_r2
from app.utils.thumbnail_utils import get_thumb_url
import app.utils.parcelamento as parcelamento_logic
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, subqueryload
import os

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
    return dict(get_thumb_url=get_thumb_url)

# ============================================================
# VITRINE PRINCIPAL (CIRURGIA A LASER: OPTIMIZED GET_SMART_CAT)
# ============================================================
@loja_bp.route('/')
@cache.cached(timeout=60, query_string=True, key_prefix='index_v7')
def index():
    termo_busca = request.args.get('q', '').strip()
    from app.produtos.configs.models import MarcaProduto
    
    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    if termo_busca:
        busca_like = f"%{termo_busca}%"
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

    lancamentos = cache.get('lancamentos_home_v4')
    if lancamentos is None:
        lancamentos = Produto.query.filter_by(visivel_loja=True)\
            .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
            .order_by(Produto.criado_em.desc()).limit(4).all()
        cache.set('lancamentos_home_v4', lancamentos, timeout=300)

    destaques = cache.get('destaques_home_v4')
    if destaques is None:
        # CIRURGIA: Removido func.random() dos destaques para poupar RAM
        destaques = Produto.query.filter_by(visivel_loja=True)\
            .options(joinedload(Produto.marca_rel), joinedload(Produto.categoria))\
            .order_by(Produto.id.desc()).limit(4).all()
        cache.set('destaques_home_v4', destaques, timeout=300)

    prateleiras = cache.get('prateleiras_home_v8')
    if prateleiras is None:
        # CIRURGIA A LASER: Reescrutura sem func.random() - Alta performance estável
        def get_smart_cat(termo, limite=4):
            cats = CategoriaProduto.query.filter(
                or_(CategoriaProduto.slug.ilike(f"%{termo}%"), CategoriaProduto.nome.ilike(f"%{termo}%"))
            ).all()
            if not cats: return []
            
            ids_alvo = list(set(
                [cat.id for cat in cats] + [s.id for cat in cats for s in cat.subcategorias]
            ))
            
            # Trazemos os registros ordenados estaticamente pelo ID descendente (Mais recentes)
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
        cache.set('prateleiras_home_v8', prateleiras, timeout=300)

    banners = cache.get('banners_home')
    if banners is None:
        banners = Banner.query.filter_by(ativo=True).order_by(Banner.ordem.asc()).all()
        cache.set('banners_home', banners, timeout=300)

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
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'robots.txt')

@loja_bp.route('/sistema/otimizar-banco-m4')
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
    
    produtos = Produto.query.filter(
        condicao_arma,
        Produto.visivel_loja == True,
        or_(
            Produto.nome.ilike(filtro),
            Produto.nome_comercial.ilike(filtro),
            Produto.codigo.ilike(filtro)
        )
    ).limit(20).all()
    
    resultado = []
    for p in produtos:
        foto = p.foto_url if p.foto_url and (p.foto_url.startswith('http') or p.foto_url.startswith('/')) else url_for('static', filename='img/sem-foto.jpg')
        resultado.append({
            'id': p.id,
            'nome': p.nome_comercial or p.nome,
            'codigo': p.codigo,
            'categoria': p.categoria.nome if p.categoria else 'N/A',
            'calibre': p.calibre_rel.nome if p.calibre_rel else 'N/A',
            'preco': float(p.preco_a_vista or 0),
            'foto': foto
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
        analise_ia = gerar_analise_comparativa(produtos_data)
        
        return jsonify({
            'produtos': produtos_data,
            'analise_ia': analise_ia
        })
    except Exception as e:
        current_app.logger.error(f'Erro no comparador: {str(e)}')
        return jsonify({'erro': f'Erro ao processar comparação: {str(e)}'}), 500

def gerar_analise_local(produtos_data):
    mais_barato = min(produtos_data, key=lambda x: x['preco_vista'])
    mais_caro = max(produtos_data, key=lambda x: x['preco_vista'])
    
    analise = f"ANÁLISE COMPARATIVA TÉCNICA\n\nMELHOR CUSTO-BENEFÍCIO\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{mais_barato['nome']}\nPreço: R$ {mais_barato['preco_vista']:,.2f}\nMarca: {mais_barato['especificacoes']['marca']}\n\nEste produto oferece o menor investimento inicial entre os comparados.\n\nCOMPARAÇÃO DETALHADA POR PREÇO\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, p in enumerate(sorted(produtos_data, key=lambda x: x['preco_vista']), 1):
        analise += f"\n{i}. {p['nome']}\n   Preço: R$ {p['preco_vista']:,.2f}\n   {p['calibre']} | {p['especificacoes']['marca']}\n"
    
    if len(produtos_data) > 1:
        diferenca = mais_caro['preco_vista'] - mais_barato['preco_vista']
        economia_pct = (diferenca / mais_caro['preco_vista']) * 100
        analise += f"\nANÁLISE FINANCEIRA\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nEscolhendo o produto mais acessível, você economiza:\n• Valor: R$ {diferenca:,.2f}\n• Percentual: {economia_pct:.1f}%\n"
    return analise

def gerar_analise_comparativa(produtos_data):
    api_key = os.getenv('GROQ_API_KEY')
    model_name = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
    
    if not api_key: return gerar_analise_local(produtos_data)
    
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        produtos_info = "\n\n".join([f"[ARMAMENTO: {p['nome'].upper()}]\nCategoria: {p['categoria']}\nCalibre: {p['calibre']}\nPreço: R$ {p['preco_vista']:.2f}\nMarca: {p['especificacoes']['marca']}" for p in produtos_data])
        
        prompt = f"Atue como um Engenheiro de Armamento e Instrutor Tático de nível Sênior. Abaixo estão os dados de armamentos. Utilize sua base de conhecimento real sobre os modelos para preencher dimensões, peso e capacidade padrão.\n\nDADOS COMERCIAIS:\n{produtos_info}\n\nESTRUTURA: 1. Resumo Técnico | 2. Comparação de Desempenho | 3. Adequação Operacional | 4. Veredito. Limite-se a 450 palavras. Não use emojis. Use os nomes reais das armas."
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Você é um perito em armamento tático. Responda em PT-BR, tom estritamente formal. Não use emojis."},
                {"role": "user", "content": prompt}
            ],
            model=model_name,
            temperature=0.3,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception:
        return gerar_analise_local(produtos_data)