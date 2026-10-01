from flask import render_template, request, jsonify, session, redirect, url_for, abort, current_app
from flask_login import current_user
from app import db
from . import carrinho_bp
from .frete import MelhorEnvioService
from .models import Carrinho, CarrinhoItem, Pedido
from app.produtos.models import Produto
from app.utils.datetime import now_local
from app.utils.r2_helpers import gerar_link_r2
from app.loja.auth_loja import get_cliente_logado
from .checkout_service import processar_checkout_pix, processar_webhook_pagarme
from .payment import calcular_snapshot_pix, obter_desconto_pix_percentual
from .frete_quotes import cart_fingerprint, issue_quote, money as money_frete, validate_quote
from app.models import Configuracao
import sqlalchemy as sa
import uuid
import re


def _cep_apenas_digitos(valor):
    """Normaliza um CEP sem confiar no formato enviado pelo navegador."""
    return ''.join(ch for ch in str(valor or '') if ch.isdigit())


def _mesma_faixa_cidade(cep_origem, cep_destino):
    """Usa os cinco primeiros dígitos do CEP para identificar a faixa postal local."""
    origem = _cep_apenas_digitos(cep_origem)
    destino = _cep_apenas_digitos(cep_destino)
    return len(origem) == 8 and len(destino) == 8 and origem[:5] == destino[:5]


def _opcao_retirada_na_loja():
    """Formato compatível com as opções retornadas pelo Melhor Envio."""
    return {
        'id': 'retirada_na_loja',
        'name': 'Retirar na Loja',
        'price': 0.0,
        'company': {'name': 'M4 Tática'},
        'delivery_range': {'min': 0, 'max': 0},
        'custom': True,
    }


# Cache global para evitar consultas repetidas de schema ao banco
_HAS_CLIENTE_ID_CACHE = None

def _assinar_opcoes_frete(opcoes, cep_destino, carrinho):
    """Anexa cotações assinadas e vinculadas à composição atual do carrinho."""
    fingerprint = cart_fingerprint(carrinho)
    assinadas = []
    for opcao in opcoes:
        empresa = (opcao.get('company') or {}).get('name') or 'Transportadora'
        nome_produto = opcao.get('name') or 'Frete'
        nome = f"{empresa} – {nome_produto}"
        if opcao.get('custom'):
            prazo = 'Retirada na loja'
        else:
            prazo_max = (opcao.get('delivery_range') or {}).get('max') or '-'
            prazo = f"Prazo: até {prazo_max} dias úteis"
        try:
            valor = money_frete(opcao.get('price'))
        except ValueError:
            continue
        option_id = str(opcao.get('id') or '')
        token, expires_at = issue_quote(
            cep_destino, option_id, nome, valor, prazo, fingerprint, current_app.secret_key
        )
        resultado = dict(opcao)
        resultado.update({
            'price': float(valor),
            'quote_id': option_id,
            'quote_name': nome,
            'quote_prazo': prazo,
            'quote_token': token,
            'quote_expires_at': expires_at,
        })
        assinadas.append(resultado)
    return assinadas

# --- FUNÇÃO DE APOIO: IDENTIFICAÇÃO DO CLIENTE ---
def get_or_create_carrinho(do_commit=True):
    """
    Recupera ou cria um carrinho vinculado à sessão ou ao cliente autenticado.
    Versão ultra-resiliente para lidar com migrations pendentes.
    """
    global _HAS_CLIENTE_ID_CACHE
    
    if 'cart_session_id' not in session:
        session['cart_session_id'] = str(uuid.uuid4())

    sid = session['cart_session_id']
    cliente = get_cliente_logado()
    uid = current_user.id if current_user.is_authenticated else None

    # Verifica se a coluna cliente_id existe para decidir a estratégia de consulta (Cacheado)
    if _HAS_CLIENTE_ID_CACHE is None:
        try:
            db.session.execute(sa.text("SELECT cliente_id FROM carrinhos LIMIT 1"))
            _HAS_CLIENTE_ID_CACHE = True
        except Exception:
            db.session.rollback()
            _HAS_CLIENTE_ID_CACHE = False
    
    has_cliente_id = _HAS_CLIENTE_ID_CACHE

    carrinho = None
    anonimo = None

    if cliente:
        if has_cliente_id:
            carrinho = db.session.query(Carrinho).filter_by(cliente_id=cliente.id).first()
            anonimo = db.session.query(Carrinho).filter_by(session_id=sid, cliente_id=None, usuario_id=None).first()
        else:
            # Sem cliente_id, usamos apenas a sessão
            carrinho = db.session.query(Carrinho).options(sa.orm.defer(Carrinho.cliente_id)).filter_by(session_id=sid, usuario_id=None).first()

        if carrinho and anonimo and carrinho.id != anonimo.id:
            # Mescla itens
            for item_anonimo in list(anonimo.items):
                item_existente = next((i for i in carrinho.items if i.produto_id == item_anonimo.produto_id), None)
                if item_existente:
                    item_existente.quantidade += item_anonimo.quantidade
                    db.session.delete(item_anonimo)
                else:
                    item_anonimo.carrinho = carrinho
            db.session.delete(anonimo)
            db.session.flush()
        elif not carrinho and anonimo:
            carrinho = anonimo
            if has_cliente_id:
                try:
                    db.session.execute(sa.text("UPDATE carrinhos SET cliente_id = :cid WHERE id = :id"), {"cid": cliente.id, "id": carrinho.id})
                except Exception: db.session.rollback()

        if not carrinho:
            carrinho = Carrinho(session_id=sid)
            db.session.add(carrinho)
            db.session.flush()
            if has_cliente_id:
                try:
                    db.session.execute(sa.text("UPDATE carrinhos SET cliente_id = :cid WHERE id = :id"), {"cid": cliente.id, "id": carrinho.id})
                except Exception: db.session.rollback()

    elif uid:
        query = db.session.query(Carrinho).filter_by(usuario_id=uid)
        if not has_cliente_id: query = query.options(sa.orm.defer(Carrinho.cliente_id))
        carrinho = query.first()
        if not carrinho:
            carrinho = Carrinho(session_id=sid, usuario_id=uid)
            db.session.add(carrinho)
    else:
        query = db.session.query(Carrinho).filter_by(session_id=sid, usuario_id=None)
        if has_cliente_id:
            query = query.filter_by(cliente_id=None)
        else:
            query = query.options(sa.orm.defer(Carrinho.cliente_id))
        carrinho = query.first()
        if not carrinho:
            carrinho = Carrinho(session_id=sid)
            db.session.add(carrinho)

    carrinho.session_id = sid
    if do_commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
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
    # do_commit=False para evitar commit duplo (um no helper e outro aqui)
    carrinho = get_or_create_carrinho(do_commit=False)
    
    # Eager load para evitar query extra no cart_count
    produto = db.session.query(Produto).filter_by(id=produto_id).first()
    if not produto:
        return jsonify({"success": False, "message": "Produto não encontrado"}), 404
    
    item = db.session.query(CarrinhoItem).filter_by(carrinho_id=carrinho.id, produto_id=produto.id).first()
    
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
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erro ao salvar no banco."}), 500
        
    nome_exibicao = produto.nome_comercial or produto.nome
    
    return jsonify({
        "success": True, 
        "cart_count": len(carrinho.items),
        "message": f"{nome_exibicao} adicionado ao arsenal!"
    })

@carrinho_bp.route('/update/<int:item_id>', methods=['POST'])
def atualizar_quantidade(item_id):
    """Atualiza quantidades ou remove itens do carrinho via AJAX."""
    try:
        item = CarrinhoItem.query.get_or_404(item_id)
        data = request.get_json() or {}
        delta = int(data.get('delta', 0))
        
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
        return jsonify({"success": False, "error": str(e)}), 500

@carrinho_bp.route('/api/frete/calcular', methods=['POST'])
def api_calcular_frete():
    """Integração com a API do Melhor Envio."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Requisição inválida."}), 400
    cep_destino = _cep_apenas_digitos(data.get('cep'))
    if len(cep_destino) != 8:
        return jsonify({"success": False, "message": "CEP inválido"}), 400
        
    carrinho = get_or_create_carrinho()
    from app.models import Configuracao
    cfg_token   = Configuracao.query.filter_by(chave='integ_melhorenvio_token').first()
    cfg_cep     = Configuracao.query.filter_by(chave='integ_melhorenvio_cep_origem').first()
    cfg_sandbox = Configuracao.query.filter_by(chave='integ_melhorenvio_sandbox').first()

    TOKEN_MELHOR_ENVIO = cfg_token.valor if cfg_token and cfg_token.valor else ''
    CEP_ORIGEM         = cfg_cep.valor   if cfg_cep   and cfg_cep.valor   else '64000000'
    USE_SANDBOX        = cfg_sandbox and cfg_sandbox.valor == '1'
    retirada_local = _mesma_faixa_cidade(CEP_ORIGEM, cep_destino)

    # A retirada local não depende do token do Melhor Envio.
    if not TOKEN_MELHOR_ENVIO and retirada_local:
        opcoes = _assinar_opcoes_frete([_opcao_retirada_na_loja()], cep_destino, carrinho)
        return jsonify({"success": True, "opcoes": opcoes})

    if not TOKEN_MELHOR_ENVIO:
        return jsonify({"success": False, "message": "Token do Melhor Envio não configurado."}), 503

    service = MelhorEnvioService(TOKEN_MELHOR_ENVIO, sandbox=USE_SANDBOX)
    resultado = service.calcular_frete(CEP_ORIGEM, cep_destino, carrinho.items) or []

    if retirada_local:
        resultado.insert(0, _opcao_retirada_na_loja())

    if resultado:
        opcoes_assinadas = _assinar_opcoes_frete(resultado, cep_destino, carrinho)
        if opcoes_assinadas:
            return jsonify({"success": True, "opcoes": opcoes_assinadas})
    return jsonify({"success": False, "message": "Não foi possível calcular o frete."}), 400

@carrinho_bp.route('/api/frete/salvar', methods=['POST'])
def salvar_frete_sessao():
    """Salva somente uma cotação válida assinada para este carrinho."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Requisição inválida."}), 400
    try:
        valor = money_frete(data.get('valor', 0))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Valor de frete inválido."}), 400
    if valor < 0:
        return jsonify({"success": False, "message": "Valor de frete inválido."}), 400
    cep = _cep_apenas_digitos(data.get('cep'))
    nome = str(data.get('nome') or '').strip()
    prazo = str(data.get('prazo') or '').strip()
    option_id = str(data.get('quote_id') or '')
    token = str(data.get('quote_token') or '')
    expires_at = data.get('quote_expires_at')
    carrinho = get_or_create_carrinho()
    fingerprint = cart_fingerprint(carrinho)
    if not validate_quote(
        cep, option_id, nome, valor, prazo, fingerprint, token, expires_at, current_app.secret_key
    ):
        return jsonify({"success": False, "message": "Cotação inválida ou expirada. Recalcule o frete."}), 400

    session['frete_valor'] = float(valor)
    session['frete_nome'] = nome
    session['frete_prazo'] = prazo
    session['frete_cep'] = cep
    session['frete_quote_id'] = option_id
    session['frete_quote_token'] = token
    session['frete_quote_expires_at'] = int(expires_at)
    session.modified = True
    return jsonify({"success": True})

@carrinho_bp.route('/api/frete/limpar', methods=['POST'])
def limpar_frete_sessao():
    """Remove a seleção de frete; sem opção válida o pedido não pode finalizar."""
    for key in (
        'frete_valor', 'frete_nome', 'frete_prazo', 'frete_cep',
        'frete_quote_id', 'frete_quote_token', 'frete_quote_expires_at',
    ):
        session.pop(key, None)
    session.modified = True
    return jsonify({"success": True})

@carrinho_bp.route('/checkout')
def checkout_view():
    """Página de checkout."""
    carrinho = get_or_create_carrinho()
    if not carrinho.items:
        return redirect(url_for('carrinho.index'))

    cliente = get_cliente_logado()
    endereco = cliente.enderecos[0] if cliente and cliente.enderecos else None
    telefone = next((c.valor for c in (cliente.contatos or []) if (c.tipo or '').lower() in ('telefone', 'celular', 'whatsapp')), '') if cliente else ''

    frete_sessao = {
        'valor': session.get('frete_valor', 0),
        'nome': session.get('frete_nome', ''),
        'prazo': session.get('frete_prazo', ''),
        'cep': session.get('frete_cep', ''),
    }
    if not session.get('loja_checkout_key'):
        session['loja_checkout_key'] = uuid.uuid4().hex
    try:
        snapshot_pix = calcular_snapshot_pix(
            carrinho.items, frete_sessao['valor'], obter_desconto_pix_percentual()
        )
    except ValueError:
        snapshot_pix = calcular_snapshot_pix(
            carrinho.items, 0, obter_desconto_pix_percentual()
        )
    pagarme_key = Configuracao.query.filter_by(chave='integ_pagarme_secret_key').first()
    pagarme_pix_configurado = bool(pagarme_key and (pagarme_key.valor or '').strip())
    checkout_disponivel = (
        pagarme_pix_configurado
        and bool(snapshot_pix['linhas'])
        and snapshot_pix['total_produtos_pix'] > 0
        and snapshot_pix['total_cobrado'] > 0
    )
    return render_template(
        'carrinho/checkout.html',
        carrinho=carrinho,
        frete_sessao=frete_sessao,
        checkout_cliente=cliente,
        checkout_endereco=endereco,
        checkout_telefone=telefone,
        snapshot_pix=snapshot_pix,
        checkout_key=session['loja_checkout_key'],
        pagarme_pix_configurado=pagarme_pix_configurado,
        checkout_disponivel=checkout_disponivel,
    )

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pedido():
    """Cria uma cobrança PIX real; cartão é bloqueado no servidor por segurança."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Requisição inválida.'}), 400
    metodo = str(data.get('metodo_pagamento') or 'pix').strip().lower()
    if metodo != 'pix':
        return jsonify({
            'success': False,
            'message': 'Pagamento por cartão está temporariamente desabilitado até confirmar o tipo da conta Pagar.me.',
        }), 409
    try:
        cliente = get_cliente_logado()
        carrinho = get_or_create_carrinho()
        resultado, status = processar_checkout_pix(data, carrinho, cliente)
        return jsonify(resultado), status
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha inesperada no checkout PIX da loja')
        return jsonify({'success': False, 'message': 'Não foi possível iniciar o pagamento PIX.'}), 500


@carrinho_bp.route('/webhook/pagarme', methods=['POST'])
def webhook_pagarme():
    """Valida eventos consultando o pedido diretamente na API autenticada."""
    resultado, status = processar_webhook_pagarme(request.get_json(silent=True))
    return jsonify(resultado), status

@carrinho_bp.route('/sucesso/<string:public_id>')
def sucesso(public_id):
    """Tela de confirmação do pedido usando ID público seguro."""
    # Busca resiliente do pedido
    has_pedido_cliente_id = False
    try:
        db.session.execute(sa.text("SELECT cliente_id FROM pedidos LIMIT 1"))
        has_pedido_cliente_id = True
    except Exception: db.session.rollback()

    query = db.session.query(Pedido).filter(Pedido.public_id == public_id)
    if not has_pedido_cliente_id:
        query = query.options(sa.orm.defer(Pedido.cliente_id))
    
    pedido = query.first_or_404()
    return render_template('carrinho/sucesso.html', pedido=pedido)
