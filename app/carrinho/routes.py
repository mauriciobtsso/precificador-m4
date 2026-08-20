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
import sqlalchemy as sa

# --- FUNÇÃO DE APOIO: IDENTIFICAÇÃO DO CLIENTE ---
def get_or_create_carrinho():
    """
    Recupera ou cria um carrinho vinculado à sessão ou ao cliente autenticado.
    Versão ultra-resiliente para lidar com migrations pendentes.
    """
    if 'cart_session_id' not in session:
        session['cart_session_id'] = str(uuid.uuid4())

    sid = session['cart_session_id']
    cliente = get_cliente_logado()
    uid = current_user.id if current_user.is_authenticated else None

    # Verifica se a coluna cliente_id existe para decidir a estratégia de consulta
    has_cliente_id = False
    try:
        db.session.execute(sa.text("SELECT cliente_id FROM carrinhos LIMIT 1"))
        has_cliente_id = True
    except Exception:
        db.session.rollback()

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
    data = request.get_json() or {}
    cep_destino = data.get('cep', '').replace('-', '')
    if not cep_destino or len(cep_destino) < 8:
        return jsonify({"success": False, "message": "CEP inválido"}), 400
        
    carrinho = get_or_create_carrinho()
    from app.models import Configuracao
    cfg_token   = Configuracao.query.filter_by(chave='integ_melhorenvio_token').first()
    cfg_cep     = Configuracao.query.filter_by(chave='integ_melhorenvio_cep_origem').first()
    cfg_sandbox = Configuracao.query.filter_by(chave='integ_melhorenvio_sandbox').first()

    TOKEN_MELHOR_ENVIO = cfg_token.valor if cfg_token and cfg_token.valor else ''
    CEP_ORIGEM         = cfg_cep.valor   if cfg_cep   and cfg_cep.valor   else '64000000'
    USE_SANDBOX        = cfg_sandbox and cfg_sandbox.valor == '1'

    if not TOKEN_MELHOR_ENVIO:
        return jsonify({"success": False, "message": "Token do Melhor Envio não configurado."}), 503

    service = MelhorEnvioService(TOKEN_MELHOR_ENVIO, sandbox=USE_SANDBOX)
    resultado = service.calcular_frete(CEP_ORIGEM, cep_destino, carrinho.items)
    
    if resultado:
        return jsonify({"success": True, "opcoes": resultado})
    return jsonify({"success": False, "message": "Não foi possível calcular o frete."}), 400

@carrinho_bp.route('/api/frete/salvar', methods=['POST'])
def salvar_frete_sessao():
    """Salva o frete escolhido na sessão."""
    data = request.get_json() or {}
    session['frete_valor'] = float(data.get('valor', 0))
    session['frete_nome'] = data.get('nome', '')
    session['frete_prazo'] = data.get('prazo', '')
    session['frete_cep'] = data.get('cep', '')
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
    return render_template('carrinho/checkout.html', carrinho=carrinho, frete_sessao=frete_sessao, checkout_cliente=cliente, checkout_endereco=endereco, checkout_telefone=telefone)

@carrinho_bp.route('/checkout/processar', methods=['POST'])
def processar_pedido():
    """Grava o pedido final."""
    try:
        data = request.get_json(silent=True) or {}
        cliente = get_cliente_logado()
        carrinho = get_or_create_carrinho()

        if not carrinho or not carrinho.items:
            return jsonify({"success": False, "message": "Carrinho vazio."}), 400

        def texto(chave): return str(data.get(chave) or '').strip()

        if cliente:
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

        if not all([nome_cliente, email_cliente, documento, cep, logradouro, numero, bairro, cidade, estado]):
            return jsonify({"success": False, "message": "Preencha todos os campos obrigatórios."}), 400

        valor_frete = float(data.get('valor_frete') or 0)
        parcelas = int(data.get('parcelas') or 1)

        # Verifica se a coluna cliente_id existe no Pedido
        has_pedido_cliente_id = False
        try:
            db.session.execute(sa.text("SELECT cliente_id FROM pedidos LIMIT 1"))
            has_pedido_cliente_id = True
        except Exception: db.session.rollback()

        pedido = Pedido(
            usuario_id=usuario_id,
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
        db.session.add(pedido)
        db.session.flush()

        if cliente_id and has_pedido_cliente_id:
            try:
                db.session.execute(sa.text("UPDATE pedidos SET cliente_id = :cid WHERE id = :id"), {"cid": cliente_id, "id": pedido.id})
            except Exception: db.session.rollback()

        for item in carrinho.items:
            p_item = PedidoItem(
                pedido_id=pedido.id,
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                preco_unitario_historico=item.preco_unitario_no_momento
            )
            db.session.add(p_item)

        # Limpa o carrinho
        for item in list(carrinho.items): db.session.delete(item)
        db.session.commit()

        session.pop('frete_valor', None)
        session.pop('frete_nome', None)
        session.pop('frete_prazo', None)
        session.pop('frete_cep', None)

        return jsonify({"success": True, "pedido_id": pedido.id, "redirect": url_for('carrinho.sucesso', pedido_id=pedido.id)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@carrinho_bp.route('/sucesso/<int:pedido_id>')
def sucesso(pedido_id):
    """Tela de confirmação do pedido."""
    # Busca resiliente do pedido
    has_pedido_cliente_id = False
    try:
        db.session.execute(sa.text("SELECT cliente_id FROM pedidos LIMIT 1"))
        has_pedido_cliente_id = True
    except Exception: db.session.rollback()

    query = db.session.query(Pedido).filter(Pedido.id == pedido_id)
    if not has_pedido_cliente_id:
        query = query.options(sa.orm.defer(Pedido.cliente_id))
    
    pedido = query.first_or_404()
    return render_template('carrinho/sucesso.html', pedido=pedido)
