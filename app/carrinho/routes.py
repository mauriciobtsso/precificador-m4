from flask import render_template, request, jsonify, session, redirect, url_for, abort
from flask_login import current_user
from app import db
from . import carrinho_bp
from .frete import MelhorEnvioService
from .models import Carrinho, CarrinhoItem, Pedido, PedidoItem
import requests
import json
from app.produtos.models import Produto
import uuid

def get_or_create_carrinho():
    # Se não tiver session_id, cria um único para o navegador do cliente
    if 'cart_session_id' not in session:
        session['cart_session_id'] = str(uuid.uuid4())
    
    sid = session['cart_session_id']
    uid = current_user.id if current_user.is_authenticated else None
    
    carrinho = Carrinho.query.filter((Carrinho.session_id == sid) | (Carrinho.usuario_id == uid)).first()
    
    if not carrinho:
        carrinho = Carrinho(session_id=sid, usuario_id=uid)
        db.session.add(carrinho)
        db.session.commit()
    return carrinho

@carrinho_bp.route('/add/<int:produto_id>', methods=['POST'])
def adicionar(produto_id):
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

@carrinho_bp.route('/')
def index():
    carrinho = get_or_create_carrinho()
    return render_template('carrinho/index.html', carrinho=carrinho)

@carrinho_bp.route('/update/<int:item_id>', methods=['POST'])
def atualizar_quantidade(item_id):
    data = request.get_json()
    delta = data.get('delta', 0)
    
    item = CarrinhoItem.query.get_or_404(item_id)
    carrinho = item.carrinho
    
    # Atualiza a quantidade
    item.quantidade += delta
    
    # Se a quantidade chegar a zero ou menos, remove o item
    if item.quantidade <= 0:
        db.session.delete(item)
        message = "Item removido do arsenal."
    else:
        message = "Quantidade atualizada."
        
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": message,
        "item_subtotal": "{:,.2f}".format(item.subtotal_avista).replace(',', 'X').replace('.', ',').replace('X', '.') if item.quantidade > 0 else 0,
        "cart_total": "{:,.2f}".format(carrinho.total_avista).replace(',', 'X').replace('.', ',').replace('X', '.'),
        "cart_count": len(carrinho.items),
        "reload": item.quantidade <= 0 # Sinaliza se a página deve recarregar para limpar a linha
    })

@carrinho_bp.route('/frete', methods=['POST'])
def calcular_frete():
    data = request.get_json()
    cep = data.get('cep')
    
    if not cep or len(cep) < 8:
        return jsonify({"success": False, "error": "CEP inválido"}), 400
        
    carrinho = get_or_create_carrinho()
    # Aqui chamaremos o Orchestrator
    valor_frete = 25.90 # Simulação
    
    return jsonify({
        "success": True,
        "opcoes": [
            {"id": "kangu_expresso", "nome": "Kangu Expresso", "valor": valor_frete, "prazo": "3 dias"},
            {"id": "melhor_envio_sedex", "nome": "Melhor Envio (SEDEX)", "valor": 32.50, "prazo": "2 dias"}
        ]
    })

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pagamento():
    data = request.get_json()
    carrinho = get_or_create_carrinho()
    
    # Orquestrador Pagar.me
    pagarme = PagarmeOrchestrator(api_key="SUA_CHAVE_AQUI")
    
    # Processamento...
    # Se for sucesso, limpamos o carrinho e criamos o Pedido no Banco
    
    return jsonify({"success": True, "redirect": "/carrinho/sucesso"})

# CHAVES PAGAR.ME (Mantenha em variáveis de ambiente no futuro)
PAGARME_SECRET_KEY = "sk_test_..." # Sua chave secreta (Sandbox)

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pedido():
    try:
        data = request.get_json()
        carrinho = Carrinho.query.filter_by(session_id=session.get('cart_session_id')).first()

        if not carrinho or not carrinho.items:
            return jsonify({"success": False, "message": "Carrinho vazio"}), 400

        # 1. CRIAR O PEDIDO NO BANCO (Status Inicial: Pendente)
        novo_pedido = Pedido(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            nome_cliente=data['nome'],
            email_cliente=data['email'],
            documento=data['documento'].replace('.', '').replace('-', '').replace('/', ''),
            telefone=data['telefone'],
            cep=data['cep'],
            logradouro=data['logradouro'],
            numero=data['numero'],
            bairro=data['bairro'],
            cidade=data['cidade'],
            estado=data['uf'],
            total_produtos=carrinho.total_avista,
            total_frete=data.get('valor_frete', 0),
            total_pedido=float(carrinho.total_avista) + float(data.get('valor_frete', 0)),
            forma_pagamento=data['metodo_pagamento'], # 'pix' ou 'credit_card'
            status='pendente'
        )

        db.session.add(novo_pedido)
        
        # Criar itens do pedido (Snapshot)
        for item in carrinho.items:
            pi = PedidoItem(
                pedido=novo_pedido,
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                preco_unitario_historico=item.preco_unitario_no_momento
            )
            db.session.add(pi)

        # 2. INTEGRAR COM PAGAR.ME
        # Payload simplificado para demonstração
        pagarme_payload = {
            "customer": {
                "name": novo_pedido.nome_cliente,
                "email": novo_pedido.email_cliente,
                "document": novo_pedido.documento,
                "type": "individual",
                "phones": {"mobile_phone": {"country_code": "55", "area_code": "86", "number": "999999999"}} # Ajustar mask
            },
            "items": [{
                "amount": int(item.preco_unitario_historico * 100),
                "description": item.produto.nome,
                "quantity": item.quantidade,
                "code": str(item.produto_id)
            } for item in novo_pedido.items],
            "payments": [{
                "payment_method": "pix" if novo_pedido.forma_pagamento == "pix" else "credit_card",
                "pix": {"expires_in": 3600} if novo_pedido.forma_pagamento == "pix" else None
                # Se for cartão, incluiria o card_token gerado pelo JS
            }]
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Basic {PAGAR_ME_AUTH_ENCODED}" # Chave em Base64
        }

        # Simulação de chamada API (Em produção use requests.post)
        # resp = requests.post("https://api.pagar.me/core/v5/orders", json=pagarme_payload, headers=headers)
        
        # Simulando Sucesso:
        novo_pedido.pagarme_id = "or_mock_12345"
        db.session.commit()

        # 3. LIMPAR CARRINHO
        for item in carrinho.items:
            db.session.delete(item)
        db.session.commit()

        return jsonify({
            "success": True, 
            "message": "Pedido gerado com sucesso!",
            "order_id": novo_pedido.id,
            "redirect": url_for('carrinho.sucesso', order_id=novo_pedido.id)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@carrinho_bp.route('/sucesso/<int:order_id>')
def sucesso(order_id):
    pedido = Pedido.query.get_or_404(order_id)
    return render_template('carrinho/sucesso.html', pedido=pedido)

@carrinho_bp.route('/webhook/pagarme', methods=['POST'])
def webhook_pagarme():
    # O Pagar.me envia os dados no corpo do POST (JSON)
    data = request.get_json()
    
    # 1. LOG TÁTICO: Registra a chegada da notificação para auditoria
    print(f"[M4-WEBHOOK] Evento recebido: {data.get('type')}")

    # 2. VALIDAÇÃO: Verifica se o evento é de sucesso no pagamento
    # Tipos comuns: 'order.paid' ou 'transaction.paid'
    if data.get('type') == 'order.paid':
        order_data = data.get('data')
        pagarme_id = order_data.get('id')
        
        # Localiza o pedido no nosso banco de dados
        pedido = Pedido.query.filter_by(pagarme_id=pagarme_id).first()
        
        if pedido:
            # 3. ATUALIZAÇÃO DE STATUS
            if pedido.status != 'pago':
                pedido.status = 'pago'
                pedido.pago_em = now_local()
                db.session.commit()
                
                # AQUI: Disparar E-mail ou WhatsApp de confirmação
                print(f"✅ Pedido #{pedido.id} confirmado e pago via Webhook!")
                
                # Se for item controlado, pode disparar alerta para o setor de documentação
                if any(item.produto.requer_documentacao for item in pedido.items):
                    print("⚠️ Alerta: Pedido contém itens controlados. Aguardando documentos.")
        else:
            print(f"❌ Pedido com Pagarme ID {pagarme_id} não encontrado no banco.")

    # O Pagar.me exige um retorno 200 OK para saber que recebemos a mensagem
    return jsonify({"status": "received"}), 200

@carrinho_bp.route('/api/frete/calcular', methods=['POST'])
def api_calcular_frete():
    data = request.get_json()
    cep_destino = data.get('cep').replace('-', '')
    carrinho = get_or_create_carrinho() # Sua função de recuperar carrinho
    
    # Configurações
    TOKEN_MELHOR_ENVIO = "SEU_TOKEN_AQUI"
    CEP_ORIGEM = "64000000" # Teresina
    
    service = MelhorEnvioService(TOKEN_MELHOR_ENVIO)
    resultado = service.calcular_frete(CEP_ORIGEM, cep_destino, carrinho.items)
    
    if resultado:
        return jsonify({"success": True, "opcoes": resultado})
    return jsonify({"success": False, "message": "Não foi possível calcular o frete."}), 400

