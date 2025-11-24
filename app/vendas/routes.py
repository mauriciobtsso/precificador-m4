from flask import render_template, request
from flask_login import login_required
from app.extensions import db
from app.vendas.models import Venda, ItemVenda
from app.clientes.models import Cliente
from . import vendas_bp
from datetime import datetime, timedelta
# ADICIONADO: 'func' para agregações no banco
from sqlalchemy import extract, func


# =========================
# LISTAGEM DE VENDAS + RESUMO
# =========================
@vendas_bp.route("/", methods=["GET", "POST"])
@login_required
def vendas():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    query = Venda.query.join(Cliente, isouter=True)

    # --- Filtros ---
    cliente_nome = request.args.get("cliente", "").strip()
    status = request.args.get("status", "").strip()
    periodo = request.args.get("periodo", "").strip()
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    if cliente_nome:
        query = query.filter(Cliente.nome.ilike(f"%{cliente_nome}%"))
    if status:
        query = query.filter(Venda.status.ilike(f"%{status}%"))

    hoje = datetime.today()
    if periodo == "7d":
        query = query.filter(Venda.data_abertura >= hoje - timedelta(days=7))
    elif periodo == "mes":
        query = query.filter(
            extract("year", Venda.data_abertura) == hoje.year,
            extract("month", Venda.data_abertura) == hoje.month
        )
    elif periodo == "personalizado" and data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Venda.data_abertura >= inicio, Venda.data_abertura < fim)
        except Exception:
            pass

    # --- Paginação (Query 1: Apenas os itens da página atual) ---
    vendas_paginadas = query.order_by(Venda.data_abertura.desc()).paginate(page=page, per_page=per_page)

    # --- Resumo agregado OTIMIZADO (Query 2: Soma direta no Banco) ---
    # Antes: query.all() -> Carregava TUDO na RAM -> Python somava. (RISCO DE CRASH)
    # Agora: query.with_entities(...) -> Banco soma e retorna só os números. (PERFORMANCE PURA)
    
    resumo_dados = query.with_entities(
        func.count(Venda.id).label('total'),
        func.sum(Venda.valor_total).label('soma_total'),
        func.sum(Venda.desconto_valor).label('soma_descontos'),
        func.sum(Venda.valor_recebido).label('soma_recebido')
    ).first()

    # Extração segura (se não houver vendas, retorna 0)
    total_vendas = resumo_dados.total or 0
    soma_total = resumo_dados.soma_total or 0
    soma_descontos = resumo_dados.soma_descontos or 0
    soma_recebido = resumo_dados.soma_recebido or 0
    
    # Cálculo de média seguro (evita divisão por zero)
    media_venda = soma_total / total_vendas if total_vendas > 0 else 0

    resumo = {
        "total_vendas": total_vendas,
        "soma_total": soma_total,
        "soma_descontos": soma_descontos,
        "soma_recebido": soma_recebido,
        "media_venda": media_venda,
    }

    return render_template(
        "vendas/index.html",
        vendas=vendas_paginadas,
        resumo=resumo,
        cliente_nome=cliente_nome,
        status=status,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


# =========================
# DETALHE DE VENDA
# =========================
@vendas_bp.route("/<int:venda_id>")
@login_required
def venda_detalhe(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    cliente = Cliente.query.get(venda.cliente_id) if venda.cliente_id else None
    itens = ItemVenda.query.filter_by(venda_id=venda.id).all()

    return render_template(
        "vendas/detalhe.html",
        venda=venda,
        cliente=cliente,
        itens=itens
    )

from flask import jsonify
from app.services.venda_service import VendaService
from app.produtos.models import Produto
from app.estoque.models import ItemEstoque

# --- TELA DE NOVA VENDA ---
@vendas_bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova_venda():
    if request.method == "POST":
        dados = request.get_json()
        try:
            venda = VendaService.criar_venda(dados, current_user)
            return jsonify({"success": True, "venda_id": venda.id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
            
    return render_template("vendas/form.html") # Criaremos este arquivo

# --- APIS INTERNAS PARA O JAVASCRIPT ---

@vendas_bp.route("/api/clientes")
@login_required
def api_buscar_clientes():
    termo = request.args.get("q", "")
    # CORREÇÃO: Trocamos Cliente.cpf por Cliente.documento
    clientes = Cliente.query.filter(
        (Cliente.nome.ilike(f"%{termo}%")) | 
        (Cliente.documento.ilike(f"%{termo}%"))
    ).limit(10).all()
    
    return jsonify([{
        "id": c.id, 
        "nome": c.nome, 
        "documento": c.documento, # Retorna o CPF/CNPJ correto
        "cr": c.cr # CORREÇÃO: Trocamos cr_numero por cr
    } for c in clientes])

@vendas_bp.route("/api/produtos")
@login_required
def api_buscar_produtos():
    termo = request.args.get("q", "")
    produtos = Produto.query.filter(
        (Produto.nome.ilike(f"%{termo}%")) | 
        (Produto.codigo.ilike(f"%{termo}%"))
    ).limit(10).all()
    
    return jsonify([{
        "id": p.id,
        "nome": p.nome,
        "preco": float(p.preco_a_vista or 0),
        # Aqui poderíamos somar o estoque total
        "estoque": 10 # Placeholder
    } for p in produtos])

@vendas_bp.route("/api/estoque/<int:produto_id>")
@login_required
def api_buscar_estoque_produto(produto_id):
    """Retorna apenas os seriais DISPONÍVEIS deste produto"""
    itens = ItemEstoque.query.filter_by(
        produto_id=produto_id, 
        status="disponivel"
    ).all()
    
    return jsonify([{
        "id": i.id,
        "serial": i.numero_serie,
        "lote": i.lote
    } for i in itens])