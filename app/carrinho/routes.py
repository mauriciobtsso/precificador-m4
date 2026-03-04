from flask import render_template, request, jsonify, session, redirect, url_for, abort
from flask_login import current_user
from app import db
from . import carrinho_bp
from .frete import MelhorEnvioService
from .models import Carrinho, CarrinhoItem, Pedido, PedidoItem
from app.produtos.models import Produto
from app.utils.datetime import now_local
from app.utils.r2_helpers import gerar_link_r2
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

def limpar_foto_url(caminho):
    """Remove o fragmento #hash e lixo do final das URLs de foto."""
    if not caminho:
        return ""
    if "#" in caminho:
        caminho = caminho.split("#")[0]
    if "%23" in caminho:
        caminho = caminho.split("%23")[0]
    return caminho

@carrinho_bp.route('/')
def index():
    """Exibe a página do carrinho com os itens e resumo."""
    carrinho = get_or_create_carrinho()
    gerar_link = lambda path: gerar_link_r2(limpar_foto_url(path)) if path else ""
    frete_sessao = {
        'valor': session.get('frete_valor', 0),
        'nome': session.get('frete_nome', ''),
        'prazo': session.get('frete_prazo', ''),
        'cep': session.get('frete_cep', ''),
    }
    return render_template('carrinho/index.html', carrinho=carrinho, gerar_link=gerar_link, frete_sessao=frete_sessao)

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

    # CORREÇÃO: usar nome amigável (nome_comercial) se disponível
    nome_exibicao = produto.nome_comercial or produto.nome
    
    return jsonify({
        "success": True, 
        "cart_count": len(carrinho.items),
        "message": f"{nome_exibicao} adicionado ao arsenal!"
    })

@carrinho_bp.route('/update/<int:item_id>', methods=['POST'])
def atualizar_quantidade(item_id):
    """
    Atualiza quantidades ou remove itens do carrinho via AJAX.
    """
    try:
        item = CarrinhoItem.query.get_or_404(item_id)
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Dados inválidos"}), 400
        
        delta = data.get('delta', 0)
        
        try:
            delta = int(delta)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Delta inválido"}), 400
        
        if delta == 0 or (item.quantidade + delta) <= 0:
            db.session.delete(item)
            db.session.commit()
            carrinho = get_or_create_carrinho()
            
            return jsonify({
                "success": True, 
                "reload": True,
                "cart_count": len(carrinho.items),
                "cart_total": f"R$ {carrinho.total_avista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            })
        
        item.quantidade += delta
        
        if item.quantidade < 1:
            item.quantidade = 1
            return jsonify({
                "success": False,
                "error": "Quantidade mínima é 1"
            }), 400
        
        db.session.commit()
        
        carrinho = item.carrinho
        
        return jsonify({
            "success": True,
            "item_subtotal": f"R$ {item.subtotal_avista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "cart_total": f"R$ {carrinho.total_avista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "cart_count": len(carrinho.items),
            "reload": False
        })
    
    except Exception as e:
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
    
    # Credenciais lidas do banco (configuradas em /admin-loja/integracoes)
    from app.models import Configuracao
    cfg_token   = Configuracao.query.filter_by(chave='integ_melhorenvio_token').first()
    cfg_cep     = Configuracao.query.filter_by(chave='integ_melhorenvio_cep_origem').first()
    cfg_sandbox = Configuracao.query.filter_by(chave='integ_melhorenvio_sandbox').first()

    TOKEN_MELHOR_ENVIO = cfg_token.valor if cfg_token and cfg_token.valor else ''
    CEP_ORIGEM         = cfg_cep.valor   if cfg_cep   and cfg_cep.valor   else '64000000'
    USE_SANDBOX        = cfg_sandbox and cfg_sandbox.valor == '1'

    if not TOKEN_MELHOR_ENVIO:
        return jsonify({"success": False, "message": "Token do Melhor Envio não configurado. Acesse /admin-loja/integracoes."}), 503

    service = MelhorEnvioService(TOKEN_MELHOR_ENVIO, sandbox=USE_SANDBOX)
    resultado = service.calcular_frete(CEP_ORIGEM, cep_destino, carrinho.items)
    
    if resultado:
        return jsonify({"success": True, "opcoes": resultado})
    return jsonify({"success": False, "message": "Não foi possível calcular o frete."}), 400


@carrinho_bp.route('/api/frete/salvar', methods=['POST'])
def salvar_frete_sessao():
    """Salva o frete escolhido na sessão para usar no checkout."""
    data = request.get_json()
    session['frete_valor'] = float(data.get('valor', 0))
    session['frete_nome'] = data.get('nome', '')
    session['frete_prazo'] = data.get('prazo', '')
    session['frete_cep'] = data.get('cep', '')
    session.modified = True
    return jsonify({"success": True})

# --- CHECKOUT E PAGAMENTO ---

@carrinho_bp.route('/checkout')
def checkout_view():
    """Página de preenchimento de endereço e pagamento."""
    carrinho = get_or_create_carrinho()
    if not carrinho.items:
        return redirect(url_for('carrinho.index'))
    frete_sessao = {
        'valor': session.get('frete_valor', 0),
        'nome': session.get('frete_nome', ''),
        'prazo': session.get('frete_prazo', ''),
        'cep': session.get('frete_cep', ''),
    }
    return render_template('carrinho/checkout.html', carrinho=carrinho, frete_sessao=frete_sessao)

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pedido():
    """Gera o pedido no banco e processa a transação no Pagar.me."""
    try:
        data = request.get_json()
        carrinho = get_or_create_carrinho()

        if not carrinho or not carrinho.items:
            return jsonify({"success": False, "message": "Carrinho vazio"}), 400

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
            forma_pagamento=data.get('metodo_pagamento'),
            status='pendente'
        )
        db.session.add(novo_pedido)
        
        for item in carrinho.items:
            pi = PedidoItem(
                pedido=novo_pedido,
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                preco_unitario_historico=item.preco_unitario_no_momento
            )
            db.session.add(pi)

        novo_pedido.pagarme_id = "or_" + str(uuid.uuid4())[:12]
        db.session.commit()

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