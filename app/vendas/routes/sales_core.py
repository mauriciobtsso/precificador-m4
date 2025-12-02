from flask import Blueprint, render_template, jsonify, request, url_for, redirect, flash, render_template_string
from flask_login import login_required, current_user
# Importações completas e corrigidas para as funções migradas:
from app.clientes.models import Cliente, Arma
from app.produtos.models import Produto
from app.vendas.models import Venda, ItemVenda
from app.estoque.models import ItemEstoque
from app.models import ModeloDocumento
from app.extensions import db
from app.utils.format_helpers import br_money
from app.services.venda_service import VendaService
from app.utils.r2_helpers import upload_file_to_r2
import json
from sqlalchemy import extract, func
from datetime import datetime, timedelta

# Inicializa o novo Blueprint para as rotas principais de vendas
sales_core = Blueprint('sales_core', __name__, template_folder='../templates')

# =================================================================
# FUNÇÃO AUXILIAR DE ESTOQUE (INJETO DE LÓGICA DE NEGÓCIO)
# =================================================================
def calcular_estoque_disponivel(produto_id):
    """
    Calcula o estoque disponível em ItemEstoque para um produto.
    Assume-se que ItemEstoque tem uma coluna 'quantidade' ou cada registro é 1 item.
    """
    from app.estoque.models import ItemEstoque 
    
    total_disponivel = db.session.query(
        func.sum(ItemEstoque.quantidade)
    ).filter(
        ItemEstoque.produto_id == produto_id,
        ItemEstoque.status == 'disponivel'
    ).scalar()

    return int(total_disponivel or 0)

# --- Lógica de Calibre (Necessária para a API de Armas) ---
def normalizar_calibre(texto):
    if not texto:
        return ""
    limpo = texto.lower().replace(".", "").replace("-", "").replace(" ", "")
    termos_para_remover = [
        "acp", "auto", "spl", "special", "win", "rem", "magnum", 
        "parabellum", "luger", "mm", "ga", "gauge", "long", "lr", "short"
    ]
    for termo in termos_para_remover:
        limpo = limpo.replace(termo, "")
    return limpo

# =================================================================
# ROTAS DE VISUALIZAÇÃO (Telas HTML)
# =================================================================

@sales_core.route("/", methods=["GET", "POST"])
@login_required
def vendas_lista():
    """Rota principal de Listagem de Vendas (migrada). Endpoint: sales_core.vendas_lista"""
    page = request.args.get("page", 1, type=int)
    per_page = 50
    query = Venda.query.join(Cliente, isouter=True) 

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

    vendas_paginadas = query.order_by(Venda.data_abertura.desc()).paginate(page=page, per_page=per_page)

    resumo_dados = query.with_entities(
        func.count(Venda.id).label('total'),
        func.sum(Venda.valor_total).label('soma_total'),
        func.sum(Venda.desconto_valor).label('soma_descontos'),
        func.sum(Venda.valor_recebido).label('soma_recebido')
    ).first()

    total_vendas = resumo_dados.total or 0
    soma_total = resumo_dados.soma_total or 0
    soma_descontos = resumo_dados.soma_descontos or 0
    soma_recebido = resumo_dados.soma_recebido or 0
    
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


@sales_core.route("/novo_pdv", methods=["GET", "POST"])
@login_required
def novo_pdv():
    """Renderiza a nova tela de vendas (PDV). Endpoint: sales_core.novo_pdv"""
    return render_template("vendas/pdv_form.html", title="Nova Venda PDV")


@sales_core.route("/<int:venda_id>")
@login_required
def venda_detalhe(venda_id):
    """Detalhe da Venda (Migrada). Endpoint: sales_core.venda_detalhe"""
    venda = Venda.query.get_or_404(venda_id)
    cliente = Cliente.query.get(venda.cliente_id) if venda.cliente_id else None
    itens = ItemVenda.query.filter_by(venda_id=venda.id).all()

    return render_template(
        "vendas/detalhe.html",
        venda=venda,
        cliente=cliente,
        itens=itens
    )


@sales_core.route("/<int:venda_id>/editar", methods=["GET", "POST"])
@login_required
def editar_venda(venda_id):
    """Edição da Venda (Migrada). Endpoint: sales_core.editar_venda"""
    venda = Venda.query.get_or_404(venda_id)
    cliente = Cliente.query.get(venda.cliente_id) if venda.cliente_id else None
    itens = ItemVenda.query.filter_by(venda_id=venda.id).all() 

    if request.method == "POST":
        pass

    itens_data = []
    for i in itens:
        detalhe_html = '<span class="text-muted small">Item de Varejo</span>'
        
        if i.item_estoque:
            if i.item_estoque.numero_serie:
                detalhe_html = f'<span class="badge bg-dark"><i class="fas fa-fingerprint"></i> Serial: {i.item_estoque.numero_serie}</span>'
            elif i.item_estoque.lote or i.item_estoque.numero_embalagem:
                detalhe_html = f'<span class="badge bg-info text-dark"><i class="fas fa-box"></i> Lote: {i.item_estoque.lote or i.item_estoque.numero_embalagem}</span>'

        if i.arma_cliente:
            craf_texto = f"{i.arma_cliente.tipo} {i.arma_cliente.calibre} ({i.arma_cliente.numero_serie or 'S/N'})"
            detalhe_html += f'<div class="mt-1 small text-primary"><i class="fas fa-id-card"></i> Ref: {craf_texto}</div>'

        if not i.item_estoque_id and i.produto and 'arma' in (i.produto.tipo_rel.nome if i.produto.tipo_rel else '').lower():
            detalhe_html = '<span class="badge bg-warning text-dark">Sob Encomenda</span>'
        
        itens_data.append({
            'produto_id': i.produto_id,
            'nome': i.produto_nome,
            'preco': float(i.valor_unitario),
            'quantidade': i.quantidade,
            'item_estoque_id': i.item_estoque_id,
            'arma_cliente_id': i.arma_cliente_id,
            'detalhe_html': detalhe_html
        })

    venda_data = {
        'id': venda.id,
        'cliente': {
            'id': cliente.id, 
            'nome': getattr(cliente, 'razao_social', cliente.nome) or cliente.nome,
            'documento': cliente.documento, 
            'cr': cliente.cr
        } if cliente else None,
        'desconto': float(venda.desconto_valor) if venda.desconto_valor else 0.0,
        'itens': itens_data
    }
    
    return render_template(
        "vendas/form.html",
        venda=venda,
        edicao=True,
        venda_json=venda_data
    )


@sales_core.route("/<int:venda_id>/excluir", methods=["POST"])
@login_required
def excluir_venda(venda_id):
    """Exclusão da Venda (Migrada). Endpoint: sales_core.excluir_venda"""
    venda = Venda.query.get_or_404(venda_id)
    try:
        db.session.delete(venda)
        db.session.commit()
        flash(f"Venda #{venda_id} excluída com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir venda: {str(e)}", "danger")
        
    return redirect(url_for("sales_core.vendas_lista"))


# =================================================================
# ROTAS DE API
# =================================================================

@sales_core.route("/api/clientes_autocomplete", methods=["GET"])
@login_required
def clientes_autocomplete():
    """Endpoint para busca rápida de cliente por nome ou documento (CPF/CNPJ)."""
    query = request.args.get("q", "").strip()
    
    if not query or len(query) < 3: 
        return jsonify([])

    clientes = Cliente.query.filter(
        (Cliente.nome.ilike(f'{query}%')) | 
        (Cliente.documento.ilike(f'%{query}%'))
    ).limit(10).all() 

    results = []
    for cliente in clientes:
        results.append({
            'id': cliente.id,
            'nome': cliente.nome,
            'documento': cliente.documento,
            'cr': cliente.cr if cliente.cr else 'N/A', 
            'status': getattr(cliente, 'status_analise', 'VERIFICAR') 
        })

    return jsonify(results)


@sales_core.route("/api/produtos_search", methods=["GET"])
@login_required
def produtos_search():
    """Endpoint para busca rápida de produtos por nome ou código de barras.
    Ajuste de atributos e conversão de tipo para Estoque e Preço.
    """
    query = request.args.get("q", "").strip()
    
    if not query or len(query) < 2:
        return jsonify([])

    # Buscamos por nome ou codigo (presumindo que 'codigo' é o campo SKU/referência)
    produtos = Produto.query.filter(
        (Produto.nome.ilike(f'%{query}%')) | 
        (Produto.codigo.ilike(f'{query}%')) 
    ).limit(15).all()

    results = []
    for produto in produtos:
        preco = float(getattr(produto, 'preco_a_vista', 0.00) or 0.00)
        
        # 🚨 CORREÇÃO DE ESTOQUE: Chamando a função de cálculo em tempo real
        estoque = calcular_estoque_disponivel(produto.id)
        
        results.append({
            'id': produto.id,
            'nome': produto.nome,
            'sku': getattr(produto, 'codigo', 'N/A'), 
            'preco_venda': preco,
            'is_controlado': getattr(produto, 'is_controlado', False),
            'estoque_disponivel': estoque,
            'calibre': getattr(produto, 'calibre', None) # Incluir calibre para o JS buscar armas
        })

    return jsonify(results)


@sales_core.route("/api/cliente/<int:cliente_id>/armas", methods=["GET"])
@login_required
def api_armas_cliente(cliente_id):
    """Retorna as armas do cliente, filtradas por calibre se especificado."""
    calibre_alvo = request.args.get("calibre")
    todas_armas = Arma.query.filter_by(cliente_id=cliente_id).all()
    
    armas_filtradas = []
    
    if calibre_alvo:
        alvo_limpo = normalizar_calibre(calibre_alvo)
        
        # Lógica de equivalência de calibre (mantida do arquivo original)
        equivalencias = {
            "9": ["9x19", "9", "380"],
            "38": ["38", "357"],
            "40": ["40", "40sw"],
        }
        compativeis = equivalencias.get(alvo_limpo, [alvo_limpo])

        for arma in todas_armas:
            arma_calibre_limpo = normalizar_calibre(arma.calibre)
            match = False
            for c in compativeis:
                if c == arma_calibre_limpo or c in arma_calibre_limpo or arma_calibre_limpo in c:
                    match = True
                    break
            
            if match:
                armas_filtradas.append(arma)
    else:
        armas_filtradas = todas_armas

    return jsonify([{
        "id": a.id,
        "descricao": f"{a.tipo or 'Arma'} {a.marca or ''} {a.modelo or ''}",
        "descricao_curta": f"{a.tipo} {a.calibre}", 
        "serial": a.numero_serie,
        "calibre": a.calibre,
        "caminho_craf": a.caminho_craf,
        "sistema": f"{a.emissor_craf or a.numero_sigma or 'S/N'}" 
    } for a in armas_filtradas])


@sales_core.route("/api/cart/add_item", methods=["POST"])
@login_required
def cart_add_item():
    """Recebe os dados do item do frontend, valida estoque/serial/CRAF e retorna o item finalizado."""
    try:
        data = request.get_json()
        
        client_id = data.get('client_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity')
        unit_price = data.get('unit_price')
        is_controlled = data.get('is_controlled', False)
        serial_lote = data.get('serial_lote')
        craf = data.get('craf')
        arma_cliente_id = data.get('arma_cliente_id') 

        if not client_id:
             return jsonify({'error': 'Cliente não selecionado. A venda requer um cliente válido.'}), 400
        if not product_id or quantity <= 0 or unit_price <= 0:
            return jsonify({'error': 'Dados do produto (ID, Qtd, Preço) são inválidos.'}), 400
        
        produto = Produto.query.get(product_id)
        if not produto:
            return jsonify({'error': 'Produto não encontrado ou inativo.'}), 404
        
        # 🚨 VALIDAÇÃO DE ESTOQUE
        estoque_atual = calcular_estoque_disponivel(product_id)
        
        if quantity > estoque_atual:
            return jsonify({'error': f'Estoque insuficiente. Disponível: {estoque_atual}. Necessário: {quantity}.'}), 400

        # 🚨 VALIDAÇÃO DE NICHO (CRAF)
        if is_controlled:
            if not serial_lote and not arma_cliente_id:
                return jsonify({'error': 'Item controlado requer Serial/Lote OU vínculo CRAF.'}), 400
            
            if produto.tipo_rel and 'munição' in produto.tipo_rel.nome.lower() and not arma_cliente_id:
                return jsonify({'error': 'Munição requer vínculo com o CRAF de uma arma do cliente.'}), 400
            
            # TODO: Lógica REAL de verificação de disponibilidade do Serial/Lote no banco de dados
            # TODO: Lógica REAL de verificação do CR do cliente

        final_item = {
            'id': f'temp-{product_id}-{hash(str(request.data))}', 
            'product_id': product_id,
            'product_name': produto.nome,
            'quantity': quantity,
            'unit_price': unit_price,
            'is_controlled': is_controlled,
            'serial': serial_lote if serial_lote and not serial_lote.startswith('LOTE-') else '',
            'lote': serial_lote if serial_lote and serial_lote.startswith('LOTE-') else '',
            'craf': craf if craf else None,
            'arma_cliente_id': arma_cliente_id,
            'total_item': round(quantity * unit_price, 2)
        }
        
        return jsonify({'success': True, 'item': final_item}), 200

    except Exception as e:
        print(f"Erro ao adicionar item ao carrinho: {e}") 
        return jsonify({'error': 'Erro interno do servidor ao processar o item.'}), 500


@sales_core.route("/api/cart/finalize_sale", methods=["POST"])
@login_required
def cart_finalize_sale():
    """Recebe o estado final do carrinho e os detalhes de pagamento para fechar a venda."""
    try:
        data = request.get_json()
        
        cart_items = data.get('items', [])
        payment_details = data.get('payment_details', {})
        total_final = data.get('total')
        client_id = data.get('client_id')

        if not cart_items:
            return jsonify({'error': 'O carrinho está vazio.'}), 400
        if total_final <= 0:
            return jsonify({'error': 'Total da venda deve ser positivo.'}), 400
        if payment_details.get('method') not in ['DINHEIRO', 'CARTAO_DEB', 'PIX', 'CARTAO_CRED', 'TRANSFERENCIA']:
             return jsonify({'error': 'Método de pagamento inválido.'}), 400
        
        # 1. Lógica Principal de Fechamento de Venda: (TODO: Implementar)
        
        sale_id = "VENDA-123456" # Simulação
        
        return jsonify({
            'success': True, 
            'message': 'Venda finalizada com sucesso!',
            'sale_id': sale_id
        }), 200

    except Exception as e:
        print(f"Erro ao finalizar venda: {e}")
        return jsonify({'error': 'Erro interno do servidor ao processar o item.'}), 500