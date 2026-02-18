from flask import render_template, abort, request, url_for
from app.loja import loja_bp
from app.loja.models_admin import Banner, PaginaInstitucional # <--- O IMPORT QUE FALTAVA
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.models import Taxa, Configuracao
from app.utils.r2_helpers import gerar_link_r2
import app.utils.parcelamento as parcelamento_logic
from sqlalchemy import or_, func

def limpar_caminho_r2(caminho):
    """
    Remove duplicidade do nome do bucket e barras extras no caminho.
    Lida com URLs completas ou caminhos internos do banco.
    """
    if not caminho:
        return ""
    
    if caminho.startswith('http' ):
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
    """Garante que categorias, configs e páginas funcionem em toda a loja."""
    # 1. Categorias do Menu
    categorias_menu = CategoriaProduto.query.filter_by(pai_id=None)\
        .order_by(CategoriaProduto.ordem_exibicao.asc(), CategoriaProduto.nome.asc()).all()
    
    # 2. PÁGINAS DO RODAPÉ (O QUE ESTAVA FALTANDO)
    from app.loja.models_admin import PaginaInstitucional
    paginas_rodape = PaginaInstitucional.query.filter_by(visivel_rodape=True).all()
    
    # 3. Configurações da Loja (CNPJ, Whats, etc)
    config_objs = Configuracao.query.filter(Configuracao.chave.like('loja_%')).all()
    loja = {c.chave: c.valor for c in config_objs}
    
    # IMPORTANTE: Retornar 'paginas_rodape' aqui para o HTML enxergar
    return dict(
        categorias_menu=categorias_menu, 
        loja=loja, 
        paginas_rodape=paginas_rodape
    )

# ============================================================
# VITRINE PRINCIPAL (ATUALIZADA COM MARCAS DINÂMICAS)
# ============================================================
@loja_bp.route('/')
def index():
    """Vitrine Principal da Loja com Banners, Marcas Dinâmicas e Prateleiras Fixas"""
    page = request.args.get('page', 1, type=int)
    termo_busca = request.args.get('q', '').strip()
    per_page = 12

    # Helper para gerar links do R2
    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    # 1. CASO DE BUSCA (Mantém comportamento de listagem)
    if termo_busca:
        busca_like = f"%{termo_busca}%"
        query = Produto.query.filter_by(visivel_loja=True).filter(
            or_(Produto.nome.ilike(busca_like), Produto.codigo.ilike(busca_like))
        )
        pagination = query.order_by(Produto.criado_em.desc()).paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('loja/index.html', 
                               produtos=pagination.items, 
                               pagination=pagination,
                               gerar_link=gerador_limpo,
                               termo_busca=termo_busca,
                               title=f"Busca: {termo_busca} - M4 Tática")

    # 2. CASO HOME (PÁGINA INICIAL ESTÁTICA/DEFINIDA)
    # Buscamos os dados base
    banners_ativos = Banner.query.filter_by(ativo=True).order_by(Banner.ordem.asc()).all()
    from app.produtos.configs.models import MarcaProduto
    marcas_home = MarcaProduto.query.filter(MarcaProduto.logo_url != None).all()

    # Lançamentos e Destaques
    lancamentos = Produto.query.filter_by(visivel_loja=True, eh_lancamento=True).order_by(Produto.criado_em.desc()).limit(4).all()
    destaques = Produto.query.filter_by(visivel_loja=True, destaque_home=True).order_by(Produto.criado_em.desc()).limit(4).all()

    # Definição da função interna para evitar NameError
    def get_by_cat_smart(termo, limit=4):
        cat = CategoriaProduto.query.filter(
            or_(CategoriaProduto.slug == termo, CategoriaProduto.nome.ilike(f"%{termo}%"))
        ).first()
        if cat:
            cat_ids = [cat.id] + [sub.id for sub in cat.subcategorias]
            return Produto.query.filter(Produto.visivel_loja == True, Produto.categoria_id.in_(cat_ids))\
                        .order_by(Produto.criado_em.desc()).limit(limit).all()
        return []

    # Montagem das Prateleiras Fixas conforme solicitado
    prateleiras = {
        "pistolas": get_by_cat_smart("pistola"),
        "rifles": get_by_cat_smart("rifle"),
        "espingardas": get_by_cat_smart("espingarda"),
        "outdoor": get_by_cat_smart("outdoor")
    }

    # IMPORTANTE: Para a Home não ser infinita, 'produtos' vai vazio se não for busca.
    # O template usará apenas lancamentos, destaques e prateleiras.
    return render_template('loja/index.html', 
                           produtos=[], # Esvazia a lista geral para não gerar scroll infinito
                           pagination=None,
                           banners=banners_ativos,
                           marcas=marcas_home,
                           lancamentos=lancamentos,
                           destaques=destaques,
                           prateleiras=prateleiras,
                           gerar_link=gerador_limpo,
                           termo_busca=None,
                           title="M4 Tática - Loja Oficial")

# ============================================================
# DETALHE DO PRODUTO
# ============================================================
@loja_bp.route('/produto/<string:slug>')
def detalhe_produto(slug):
    """Página de Detalhes — Foco em Conversão e Dados Técnicos"""
    produto = Produto.query.filter_by(slug=slug, visivel_loja=True).first_or_404()
    
    # 1. Executa a lógica financeira do Model
    precos = produto.calcular_precos()
    
    # 2. GERAÇÃO DE PARCELAMENTO (O QUE FALTAVA)
    # Buscamos as taxas cadastradas no banco para calcular a tabela real
    valor_base = float(precos.get('preco_a_vista') or 0.0)
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    opcoes_parcelamento = parcelamento_logic.gerar_linhas_parcelas(valor_base, taxas)
    
    # Pega a linha de 12x especificamente para o resumo no topo
    parcela_12x = next((item for item in opcoes_parcelamento if item["rotulo"] == "12x"), None)
    
    # 3. Produtos Relacionados
    relacionados = Produto.query.filter(
        Produto.categoria_id == produto.categoria_id, 
        Produto.id != produto.id,
        Produto.visivel_loja == True
    ).order_by(func.random()).limit(4).all()

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
    
    # Parâmetros de Filtro e Ordenação
    marca_id = request.args.get('marca', type=int)
    calibre_id = request.args.get('calibre', type=int)
    preco_max = request.args.get('preco_max', type=float)
    sort = request.args.get('sort', 'novidades') # novidades, menor_preco, maior_preco
    page = request.args.get('page', 1, type=int)
    
    # Query Base (considerando subcategorias)
    cat_ids = [categoria_obj.id] + [sub.id for sub in categoria_obj.subcategorias]
    query = Produto.query.filter(Produto.categoria_id.in_(cat_ids), Produto.visivel_loja == True)

    # Aplicação de Filtros
    if marca_id: query = query.filter(Produto.marca_id == marca_id)
    if calibre_id: query = query.filter(Produto.calibre_id == calibre_id)
    if preco_max: query = query.filter(Produto.preco_a_vista <= preco_max)

    # Ordenação
    if sort == 'menor_preco':
        query = query.order_by(Produto.preco_a_vista.asc())
    elif sort == 'maior_preco':
        query = query.order_by(Produto.preco_a_vista.desc())
    else: # novidades
        query = query.order_by(Produto.criado_em.desc())

    pagination = query.paginate(page=page, per_page=12)

    # Dados para a Sidebar (Somente o que existe nesta categoria)
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
    """Exibe uma página institucional (Ex: política de privacidade)"""
    pagina = PaginaInstitucional.query.filter_by(slug=slug).first_or_404()
    return render_template('loja/pagina_institucional.html', pagina=pagina)

@loja_bp.route('/fale-conosco')
def fale_conosco():
    """Página de contato utilizando os dados dinâmicos da loja"""
    return render_template('loja/fale_conosco.html', title="Fale Conosco - M4 Tática")


