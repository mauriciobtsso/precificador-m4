from flask import render_template, abort, request, url_for
from app.loja import loja_bp
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.models import Taxa
from app.utils.r2_helpers import gerar_link_r2
import app.utils.parcelamento as parcelamento_logic
from sqlalchemy import or_

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
    """Garante que o menu de categorias funcione em qualquer página da loja."""
    # Busca categorias principais (pai_id=None) para o menu superior e lateral
    categorias_menu = CategoriaProduto.query.filter_by(pai_id=None)\
        .order_by(CategoriaProduto.ordem_exibicao.asc(), CategoriaProduto.nome.asc()).all()
    return dict(categorias_menu=categorias_menu)

# ============================================================
# VITRINE PRINCIPAL
# ============================================================
@loja_bp.route('/')
def index():
    """Vitrine Principal da Loja com Prateleiras (Home) ou Busca"""
    page = request.args.get('page', 1, type=int)
    termo_busca = request.args.get('q', '').strip()
    per_page = 12

    # Gerador de links assinado do R2
    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    # CASO 1: É UMA BUSCA DO USUÁRIO
    if termo_busca:
        busca_like = f"%{termo_busca}%"
        query = Produto.query.filter_by(visivel_loja=True).filter(
            or_(
                Produto.nome.ilike(busca_like),
                Produto.codigo.ilike(busca_like)
            )
        )
        pagination = query.order_by(Produto.criado_em.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('loja/index.html', 
                               produtos=pagination.items, 
                               pagination=pagination,
                               gerar_link=gerador_limpo,
                               termo_busca=termo_busca,
                               title=f"Busca: {termo_busca} - M4 Tática")

    # CASO 2: PÁGINA INICIAL (HOME) - Montar Prateleiras
    if page == 1:
        # Lançamentos e Destaques
        lancamentos = Produto.query.filter_by(visivel_loja=True, eh_lancamento=True).limit(4).all()
        destaques = Produto.query.filter_by(visivel_loja=True, destaque_home=True).limit(4).all()

        # Função auxiliar para buscar produtos por nome de categoria (slug ou nome)
        def get_by_cat(nome_slug):
            cat = CategoriaProduto.query.filter(
                or_(CategoriaProduto.nome.ilike(f"%{nome_slug}%"), CategoriaProduto.slug == nome_slug)
            ).first()
            if cat:
                return Produto.query.filter_by(visivel_loja=True, categoria_id=cat.id).limit(4).all()
            return []

        # Prateleiras baseadas no print enviado
        prateleiras = {
            "pistolas": get_by_cat("pistolas"),
            "rifles": get_by_cat("rifles"),
            "espingardas": get_by_cat("espingardas"),
            "revolveres": get_by_cat("revolveres"),
            "municoes": get_by_cat("municoes"),
            "outdoor": get_by_cat("outdoor")
        }
    else:
        lancamentos = destaques = None
        prateleiras = {}

    # Paginação para o grid geral no rodapé da Home
    pagination = Produto.query.filter_by(visivel_loja=True)\
        .order_by(Produto.criado_em.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('loja/index.html', 
                           produtos=pagination.items, 
                           pagination=pagination,
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
    """Página de Detalhes com Cálculo Oficial de Parcelas"""
    produto = Produto.query.filter_by(slug=slug, visivel_loja=True).first_or_404()
    precos = produto.calcular_precos()
    
    valor_base = float(precos.get('preco_a_vista') or produto.preco_a_vista or 0.0)
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    opcoes_parcelamento = parcelamento_logic.gerar_linhas_parcelas(valor_base, taxas)
    
    parcela_12x = next((item for item in opcoes_parcelamento if item["rotulo"] == "12x"), None)

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
                           meta_title=produto.meta_title or produto.nome,
                           meta_desc=produto.meta_description)

# ============================================================
# PÁGINA DE CATEGORIA
# ============================================================
@loja_bp.route('/categoria/<string:slug_categoria>')
def categoria(slug_categoria):
    """Listagem de Produtos filtrada por Categoria"""
    categoria_obj = CategoriaProduto.query.filter_by(slug=slug_categoria).first_or_404()
    
    page = request.args.get('page', 1, type=int)
    per_page = 12

    pagination = Produto.query.filter_by(categoria_id=categoria_obj.id, visivel_loja=True)\
        .order_by(Produto.criado_em.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    gerador_limpo = lambda path: gerar_link_r2(limpar_caminho_r2(path))

    return render_template('loja/index.html', 
                           produtos=pagination.items, 
                           pagination=pagination,
                           categoria_ativa=categoria_obj,
                           gerar_link=gerador_limpo,
                           title=f"{categoria_obj.nome} - M4 Tática")