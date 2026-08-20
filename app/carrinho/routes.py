from flask import render_template, request, jsonify, session, redirect, url_for, abort, current_app
from flask_login import current_user
from app import db
from . import carrinho_bp
from .frete import MelhorEnvioService
from .models import Carrinho, CarrinhoItem, Pedido, PedidoItem
from app.produtos.models import Produto
from app.utils.datetime import now_local
from app.utils.r2_helpers import gerar_link_r2
from app.loja.auth_loja import get_cliente_logado
import requests
import json
import uuid

# --- FUNÇÃO DE APOIO: IDENTIFICAÇÃO DO CLIENTE ---
def get_or_create_carrinho():
    """Obtém o carrinho correto para visitante, admin ou cliente da loja.

    A autenticação da loja usa ``loja_cliente_id`` e é independente do
    Flask-Login. O carrinho anônimo da mesma sessão é incorporado ao carrinho
    do cliente no primeiro acesso autenticado, evitando perda de itens.
    """
    if 'cart_session_id' not in session:
        session['cart_session_id'] = str(uuid.uuid4())

    sid = session['cart_session_id']
    cliente = get_cliente_logado()
    uid = current_user.id if current_user.is_authenticated else None

    if cliente:
        carrinho = Carrinho.query.filter_by(cliente_id=cliente.id).first()
        anonimo = Carrinho.query.filter_by(
            session_id=sid, cliente_id=None
        ).first()

        if carrinho and anonimo and carrinho.id != anonimo.id:
            # Mescla o carrinho criado antes do login no carrinho persistente.
            for item_anonimo in list(anonimo.items):
                item_existente = next(
                    (item for item in carrinho.items
                     if item.produto_id == item_anonimo.produto_id),
                    None,
                )
                if item_existente:
                    item_existente.quantidade += item_anonimo.quantidade
                    db.session.delete(item_anonimo)
                else:
                    item_anonimo.carrinho = carrinho
            db.session.delete(anonimo)
            db.session.flush()
        elif not carrinho and anonimo:
            carrinho = anonimo
            carrinho.cliente_id = cliente.id

        if not carrinho:
            carrinho = Carrinho(
                session_id=sid,
                cliente_id=cliente.id,
            )
            db.session.add(carrinho)

    elif uid:
        carrinho = Carrinho.query.filter_by(usuario_id=uid).first()
        if not carrinho:
            carrinho = Carrinho(session_id=sid, usuario_id=uid)
            db.session.add(carrinho)
    else:
        carrinho = Carrinho.query.filter_by(
            session_id=sid, cliente_id=None, usuario_id=None
        ).first()
        if not carrinho:
            carrinho = Carrinho(session_id=sid)
            db.session.add(carrinho)

    carrinho.session_id = sid
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

    cliente = get_cliente_logado()
    endereco = cliente.enderecos[0] if cliente and cliente.enderecos else None
    telefone = ''
    if cliente:
        telefone = next(
            (contato.valor for contato in (cliente.contatos or [])
             if (contato.tipo or '').lower() in ('telefone', 'celular', 'whatsapp')),
            '',
        )

    frete_sessao = {
        'valor': session.get('frete_valor', 0),
        'nome': session.get('frete_nome', ''),
        'prazo': session.get('frete_prazo', ''),
        'cep': session.get('frete_cep', ''),
    }
    return render_template(
        'carrinho/checkout.html',
        carrinho=carrinho,
        frete_sessao=frete_sessao,
        checkout_cliente=cliente,
        checkout_endereco=endereco,
        checkout_telefone=telefone,
    )

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pedido():
    """Valida e grava o pedido usando a identidade real da loja quando houver."""
    try:
        data = request.get_json(silent=True) or {}
        cliente = get_cliente_logado()
        carrinho = get_or_create_carrinho()

        if not carrinho or not carrinho.items:
            return jsonify({"success": False, "message": "Carrinho vazio."}), 400

        def texto(chave):
            return str(data.get(chave) or '').strip()

        if cliente:
            # Não confiamos em nome, e-mail ou CPF enviados pelo navegador.
            nome_cliente = (cliente.nome or '').strip()
            email_cliente = (cliente.email_login or '').strip().lower()
            documento = ''.join(filter(str.isdigit, cliente.documento or ''))
            cliente_id = cliente.id
            usuario_id = None
        else:
            nome_cliente = texto('nome')
            email_cliente = texto('email').lower()
            documento = ''.join(filter(str.isdigit, texto('documento')))
            cliente_id = None
            usuario_id = current_user.id if current_user.is_authenticated else None

        cep = ''.join(filter(str.isdigit, texto('cep')))
        logradouro = texto('logradouro')
        numero = texto('numero')
        bairro = texto('bairro')
        cidade = texto('cidade')
        estado = texto('uf').upper()
        telefone = texto('telefone')

        obrigatorios = {
            'nome': nome_cliente,
            'e-mail': email_cliente,
            'documento': documento,
            'CEP': cep,
            'logradouro': logradouro,
            'número': numero,
            'bairro': bairro,
            'cidade': cidade,
            'UF': estado,
        }
        faltantes = [nome for nome, valor in obrigatorios.items() if not valor]
        if faltantes:
            return jsonify({
                "success": False,
                "message": "Preencha os campos obrigatórios: " + ', '.join(faltantes) + ".",
            }), 400

        try:
            valor_frete = max(0.0, float(data.get('valor_frete') or 0))
            parcelas = max(1, min(12, int(data.get('parcelas') or 1)))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Valores de frete ou parcelas inválidos."}), 400

        novo_pedido = Pedido(
            usuario_id=usuario_id,
            cliente_id=cliente_id,
            nome_cliente=nome_cliente,
            email_cliente=email_cliente,
            documento=documento,
            telefone=telefone,
            cep=cep,
            logradouro=logradouro,
            numero=numero,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            total_produtos=carrinho.total_avista,
            total_frete=valor_frete,
            total_pedido=float(carrinho.total_avista) + valor_frete,
            forma_pagamento=(texto('metodo_pagamento') or 'pix'),
            parcelas=parcelas,
            status='pendente'
        )
        db.session.add(novo_pedido)
        carrinho.cliente_id = cliente_id
        
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

        for item in list(carrinho.items):
            db.session.delete(item)
        session.pop('frete_valor', None)
        session.pop('frete_nome', None)
        session.pop('frete_prazo', None)
        session.pop('frete_cep', None)
        session['ultimo_pedido_id'] = novo_pedido.id
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
    """Página final de confirmação, limitada ao pedido recém-criado pelo visitante."""
    pedido = Pedido.query.get_or_404(order_id)
    cliente = get_cliente_logado()
    if cliente:
        if pedido.cliente_id != cliente.id:
            abort(404)
    elif session.get('ultimo_pedido_id') != order_id:
        abort(404)
    return render_template('carrinho/sucesso.html', pedido=pedido)

@carrinho_bp.route('/webhook/pagarme', methods=['POST'])
def webhook_pagarme():
    """Recebe avisos automáticos de pagamento aprovado do Pagar.me."""
    import hmac
    import hashlib

    # Valida assinatura HMAC-SHA256 do Pagar.me
    secret = os.getenv('PAGARME_WEBHOOK_SECRET', '')
    if not secret:
        current_app.logger.warning("[WEBHOOK] PAGARME_WEBHOOK_SECRET não configurado — webhook recusado.")
        return jsonify({"error": "Webhook não configurado."}), 503

    signature_header = request.headers.get('X-Hub-Signature', '')
    payload = request.get_data()
    expected_sig = 'sha256=' + hmac.new(
        secret.encode('utf-8'), payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature_header):
        current_app.logger.warning("[WEBHOOK] Assinatura inválida recebida no webhook Pagar.me.")
        return jsonify({"error": "Assinatura inválida."}), 401

    try:
        data = request.get_json(force=True)
        if data and data.get('type') == 'order.paid':
            order_data = data.get('data', {})
            pedido = Pedido.query.filter_by(pagarme_id=order_data.get('id')).first()
            if pedido:
                pedido.status = 'pago'
                pedido.pago_em = now_local()
                db.session.commit()
    except Exception as e:
        current_app.logger.error(f"[WEBHOOK] Erro ao processar webhook Pagar.me: {e}")
        return jsonify({"error": "Erro interno."}), 500

    return jsonify({"status": "received"}), 200