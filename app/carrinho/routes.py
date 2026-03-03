from flask import render_template, request, jsonify, session, redirect, url_for, abort
from flask_login import current_user
from app import db
from . import carrinho_bp
from .frete import MelhorEnvioService
from .models import Carrinho, CarrinhoItem, Pedido, PedidoItem
from app.produtos.models import Produto
from app.utils.datetime import now_local
import requests
import json
import uuid

# --- FUNÇÃO DE APOIO: IDENTIFICAÇÃO DO CLIENTE ---
def get_or_create_carrinho():
    """
    Recupera o carrinho pela sessão (browser) ou pelo usuário logado.
    Garante que o cliente não perca os itens ao navegar.
    """
    if 'cart_session_id' not in session:
        session['cart_session_id'] = str(uuid.uuid4())
    
    sid = session['cart_session_id']
    uid = current_user.id if current_user.is_authenticated else None
    
    # Busca carrinho vinculado à sessão ou ao ID do usuário
    carrinho = Carrinho.query.filter((Carrinho.session_id == sid) | (Carrinho.usuario_id == uid)).first()
    
    if not carrinho:
        carrinho = Carrinho(session_id=sid, usuario_id=uid)
        db.session.add(carrinho)
        db.session.commit()
    return carrinho

# --- ROTAS PRINCIPAIS DO CARRINHO ---

@carrinho_bp.route('/')
def index():
    """Exibe a página do carrinho com os itens e resumo."""
    carrinho = get_or_create_carrinho()
    return render_template('carrinho/index.html', carrinho=carrinho)

@carrinho_bp.route('/add/<int:produto_id>', methods=['POST'])
def adicionar(produto_id):
    """Adiciona um produto ao arsenal (via AJAX)."""
    carrinho = get_or_create_carrinho()
    produto = Produto.query.get_or_404(produto_id)
    
    item = CarrinhoItem.query.filter_by(carrinho_id=carrinho.id, produto_id=produto.id).first()
    
    if item:
        item.quantidade += 1
    else:
        item = CarrinhoItem(
            carrinho_id=carrinho.id, 
            produto_id=produto.id, 
            quantidade=1,
            preco_unitario_no_momento=produto.preco_a_vista
        )
        db.session.add(item)
    
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "cart_count": len(carrinho.items),
        "message": f"{produto.nome} adicionado ao arsenal!"
    })

@carrinho_bp.route('/update/<int:item_id>', methods=['POST'])
def atualizar_quantidade(item_id):
    """
    Atualiza quantidades ou remove itens do carrinho via AJAX.
    
    CORREÇÃO: Melhorado tratamento de erros e validações para garantir
    que os botões de adicionar/diminuir e excluir funcionem corretamente.
    """
    try:
        # Validar que o item existe
        item = CarrinhoItem.query.get_or_404(item_id)
        
        # Obter dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Dados inválidos"}), 400
        
        delta = data.get('delta', 0)
        
        # Validar que delta é um inteiro
        try:
            delta = int(delta)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Delta inválido"}), 400
        
        # LÓGICA DE EXCLUSÃO: Se delta for 0 ou a quantidade cair abaixo de 1
        if delta == 0 or (item.quantidade + delta) <= 0:
            db.session.delete(item)
            db.session.commit()
            carrinho = get_or_create_carrinho()
            
            return jsonify({
                "success": True, 
                "reload": True,  # Sinaliza que deve recarregar a página
                "cart_count": len(carrinho.items),
                "cart_total": f"R$ {carrinho.total_avista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            })
        
        # ATUALIZAR QUANTIDADE: Incrementar ou decrementar
        item.quantidade += delta
        
        # Validar que a quantidade nunca fica negativa (proteção extra)
        if item.quantidade < 1:
            item.quantidade = 1
            return jsonify({
                "success": False,
                "error": "Quantidade mínima é 1"
            }), 400
        
        db.session.commit()
        
        # Recarregar o carrinho para obter dados atualizados
        carrinho = item.carrinho
        
        return jsonify({
            "success": True,
            "item_subtotal": f"R$ {item.subtotal_avista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "cart_total": f"R$ {carrinho.total_avista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "cart_count": len(carrinho.items),
            "reload": False  # Não precisa recarregar a página
        })
    
    except Exception as e:
        # Log do erro para debugging
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erro ao atualizar carrinho: {str(e)}"
        }), 500

# --- LOGÍSTICA E FRETE REAL ---

@carrinho_bp.route('/api/frete/calcular', methods=['POST'])
def api_calcular_frete():
    """Integração com a API do Melhor Envio usando peso e dimensões reais."""
    data = request.get_json()
    cep_destino = data.get('cep', '').replace('-', '')
    
    if not cep_destino or len(cep_destino) < 8:
        return jsonify({"success": False, "message": "CEP inválido"}), 400
        
    carrinho = get_or_create_carrinho()
    
    # Credenciais de Logística
    TOKEN_MELHOR_ENVIO = "SEU_TOKEN_REAL_AQUI"
    CEP_ORIGEM = "64000000" # Teresina-PI
    
    service = MelhorEnvioService(TOKEN_MELHOR_ENVIO)
    resultado = service.calcular_frete(CEP_ORIGEM, cep_destino, carrinho.items)
    
    if resultado:
        return jsonify({"success": True, "opcoes": resultado})
    return jsonify({"success": False, "message": "Não foi possível calcular o frete."}), 400

# --- CHECKOUT E PAGAMENTO (PAGAR.ME) ---

@carrinho_bp.route('/checkout')
def checkout_view():
    """Página de preenchimento de endereço e pagamento."""
    carrinho = get_or_create_carrinho()
    if not carrinho.items:
        return redirect(url_for('carrinho.index'))
    return render_template('carrinho/checkout.html', carrinho=carrinho)

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pedido():
    """Gera o pedido no banco e processa a transação no Pagar.me."""
    try:
        data = request.get_json()
        carrinho = get_or_create_carrinho()

        if not carrinho or not carrinho.items:
            return jsonify({"success": False, "message": "Carrinho vazio"}), 400

        # 1. Snapshot do Pedido (Dados que nunca mudam após a compra)
        novo_pedido = Pedido(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            nome_cliente=data.get('nome'),
            email_cliente=data.get('email'),
            documento=data.get('documento', '').replace('.', '').replace('-', '').replace('/', ''),
            telefone=data.get('telefone'),
            cep=data.get('cep'),
            logradouro=data.get('logradouro'),
            numero=data.get('numero'),
            bairro=data.get('bairro'),
            cidade=data.get('cidade'),
            estado=data.get('uf'),
            total_produtos=carrinho.total_avista,
            total_frete=float(data.get('valor_frete', 0)),
            total_pedido=float(carrinho.total_avista) + float(data.get('valor_frete', 0)),
            forma_pagamento=data.get('metodo_pagamento'), # 'pix' ou 'credit_card'
            status='pendente'
        )
        db.session.add(novo_pedido)
        
        # 2. Registra os itens vendidos (Snapshot de preço)
        for item in carrinho.items:
            pi = PedidoItem(
                pedido=novo_pedido,
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                preco_unitario_historico=item.preco_unitario_no_momento
            )
            db.session.add(pi)

        # 3. Integração Pagar.me (Simulação para Homologação)
        # Em produção, aqui entraria o requests.post para a API v5 do Pagar.me
        novo_pedido.pagarme_id = "or_" + str(uuid.uuid4())[:12]
        db.session.commit()

        # 4. Limpeza de Arsenal (Esvazia o carrinho após gerar o pedido)
        for item in carrinho.items:
            db.session.delete(item)
        db.session.commit()

        return jsonify({
            "success": True, 
            "message": "Operação realizada!",
            "order_id": novo_pedido.id,
            "redirect": url_for('carrinho.sucesso', order_id=novo_pedido.id)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@carrinho_bp.route('/sucesso/<int:order_id>')
def sucesso(order_id):
    """Página final de confirmação com QR Code (PIX) ou status do cartão."""
    pedido = Pedido.query.get_or_404(order_id)
    return render_template('carrinho/sucesso.html', pedido=pedido)

@carrinho_bp.route('/webhook/pagarme', methods=['POST'])
def webhook_pagarme():
    """Recebe avisos automáticos de pagamento aprovado do Pagar.me."""
    data = request.get_json()
    if data.get('type') == 'order.paid':
        order_data = data.get('data')
        pedido = Pedido.query.filter_by(pagarme_id=order_data.get('id')).first()
        if pedido:
            pedido.status = 'pago'
            pedido.pago_em = now_local()
            db.session.commit()
    return jsonify({"status": "received"}), 200
