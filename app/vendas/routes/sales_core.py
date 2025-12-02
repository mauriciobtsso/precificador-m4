# app/vendas/routes/sales_core.py

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
# 🚨 CORREÇÃO DO ERRO: Importar modelos de seus respectivos módulos,
# em vez de tentar importar 'Cliente' e 'Produto' de 'app.models'
from app.clientes.models import Cliente 
from app.produtos.models import Produto
from app.extensions import db 
import json

# Inicializa o novo Blueprint para as rotas principais de vendas
sales_core = Blueprint('sales_core', __name__, template_folder='../templates') 

# =================================================================
# ROTAS DE VISUALIZAÇÃO
# =================================================================

@sales_core.route("/novo_pdv", methods=["GET", "POST"])
@login_required
def novo_pdv():
    """Renderiza a nova tela de vendas (PDV)."""
    return render_template("vendas/pdv_form.html", title="Nova Venda PDV")

# =================================================================
# ROTAS DE API (BUSCA DE DADOS)
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
    """Endpoint para busca rápida de produtos por nome ou código de barras."""
    query = request.args.get("q", "").strip()
    
    if not query or len(query) < 2:
        return jsonify([])

    produtos = Produto.query.filter(
        (Produto.nome.ilike(f'%{query}%')) | 
        (Produto.codigo_interno.ilike(f'{query}%')) |
        (Produto.codigo_barras.ilike(f'{query}%'))
    ).limit(15).all()

    results = []
    for produto in produtos:
        results.append({
            'id': produto.id,
            'nome': produto.nome,
            'sku': produto.codigo_interno,
            'preco_venda': float(produto.preco_venda) if produto.preco_venda else 0.00,
            'is_controlado': getattr(produto, 'is_controlado', False),
            'estoque_disponivel': getattr(produto, 'estoque_atual', 0), 
        })

    return jsonify(results)

# =================================================================
# ROTAS DE API (MANIPULAÇÃO DO CARRINHO)
# =================================================================

@sales_core.route("/api/cart/add_item", methods=["POST"])
@login_required
def cart_add_item():
    """Recebe os dados do item do frontend, valida estoque/serial/CRAF e retorna o item finalizado."""
    try:
        # 1. Recebe os dados JSON do item
        data = request.get_json()
        
        # 2. Extrai dados essenciais para validação
        client_id = data.get('client_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity')
        unit_price = data.get('unit_price')
        is_controlled = data.get('is_controlled', False)
        serial_lote = data.get('serial_lote')
        craf = data.get('craf')

        # 3. Validação Básica de Negócio
        if not client_id:
             return jsonify({'error': 'Cliente não selecionado. A venda requer um cliente válido.'}), 400
        if not product_id or quantity <= 0 or unit_price <= 0:
            return jsonify({'error': 'Dados do produto (ID, Qtd, Preço) são inválidos.'}), 400
        
        produto = Produto.query.get(product_id)
        if not produto:
            return jsonify({'error': 'Produto não encontrado ou inativo.'}), 404
        
        # 4. Validação de Estoque
        estoque_atual = getattr(produto, 'estoque_atual', 0)
        if quantity > estoque_atual:
            return jsonify({'error': f'Estoque insuficiente. Disponível: {estoque_atual}. Necessário: {quantity}.'}), 400

        # 5. Validação de Itens Controlados (Lógica do Nicho)
        if is_controlled:
            if not serial_lote:
                return jsonify({'error': 'Item controlado requer Serial ou Lote preenchido.'}), 400
            
            # TODO: Lógica REAL de verificação de disponibilidade do Serial/Lote no banco de dados

            # TODO: Lógica REAL de verificação do CR do cliente

        # 6. Preparação do Item Final 
        
        # Cria um objeto final para o frontend (pode incluir mais campos de banco de dados)
        final_item = {
            # ID temporário para o frontend
            'id': f'temp-{product_id}-{hash(str(request.data))}', 
            'product_id': product_id,
            'product_name': produto.nome,
            'quantity': quantity,
            'unit_price': unit_price,
            'is_controlled': is_controlled,
            'serial': serial_lote if serial_lote and not serial_lote.startswith('LOTE-') else '',
            'lote': serial_lote if serial_lote and serial_lote.startswith('LOTE-') else '',
            'craf': craf if craf else None,
            'total_item': round(quantity * unit_price, 2)
        }
        
        # 7. Retorna o item formatado
        return jsonify({'success': True, 'item': final_item}), 200

    except Exception as e:
        # Loga o erro para debug
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
        
        # Simulando o sucesso
        sale_id = "VENDA-123456" # ID real gerado pelo ORM
        
        return jsonify({
            'success': True, 
            'message': 'Venda finalizada com sucesso!',
            'sale_id': sale_id
        }), 200

    except Exception as e:
        # db.session.rollback() # Em caso de falha
        print(f"Erro ao finalizar venda: {e}")
        return jsonify({'error': 'Erro interno ao finalizar a venda. Transação cancelada.'}), 500