# ============================================================
# MÓDULO: ESTOQUE — Munições (Gerenciamento Avançado)
# ============================================================

from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy import func, desc, literal
from app import db
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from app.vendas.models import ItemVenda, Venda
from app.compras.models import CompraItem, CompraNF
from app.clientes.models import Cliente
from app.utils.datetime import now_local
from datetime import datetime, date, time
import json 

# ==========================================================
# LISTAGEM (INDEX)
# ==========================================================
@estoque_bp.route("/municoes")
@login_required
def municoes_listar():
    # Saldo Real (Entradas - Saídas)
    sq_entradas = db.session.query(ItemEstoque.produto_id, func.sum(ItemEstoque.quantidade).label('total_entrada'))\
     .filter_by(tipo_item="municao", status="disponivel").group_by(ItemEstoque.produto_id).subquery()

    sq_saidas = db.session.query(ItemVenda.produto_id, func.sum(ItemVenda.quantidade).label('total_saida'))\
     .join(Venda).filter(Venda.status != 'Cancelada').group_by(ItemVenda.produto_id).subquery()

    produtos_estoque = db.session.query(
        Produto,
        (func.coalesce(sq_entradas.c.total_entrada, 0) - func.coalesce(sq_saidas.c.total_saida, 0)).label('saldo_real')
    ).outerjoin(sq_entradas, Produto.id == sq_entradas.c.produto_id)\
     .outerjoin(sq_saidas, Produto.id == sq_saidas.c.produto_id)\
     .filter(func.coalesce(sq_entradas.c.total_entrada, 0) > 0)\
     .order_by(Produto.nome).all()

    saldo_geral = sum(row.saldo_real for row in produtos_estoque)
    total_saida_geral = db.session.query(func.sum(ItemVenda.quantidade)).join(Venda).filter(Venda.status != 'Cancelada').scalar() or 0
    
    totais = {"disponivel": int(saldo_geral), "vendida": int(total_saida_geral), "total": int(saldo_geral + total_saida_geral)}

    return render_template("estoque/municoes/listar.html", itens=produtos_estoque, totais=totais)


# ==========================================================
# GERENCIAR PRODUTO (DETALHES E HISTÓRICO)
# ==========================================================
@estoque_bp.route("/municoes/produto/<int:produto_id>")
@login_required
def municoes_gerenciar_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)

    # 1. Estoque Físico (Embalagens)
    estoque_atual = ItemEstoque.query.filter_by(
        tipo_item="municao", 
        produto_id=produto_id, 
        status="disponivel"
    ).order_by(ItemEstoque.data_entrada.desc()).all()

    saldo_a_classificar = sum(i.quantidade for i in estoque_atual if not i.numero_embalagem or i.numero_embalagem == 'ATACADO')
    
    # Validação de Saldo (Para exibir corretamente o "A Classificar")
    total_saidas = db.session.query(func.sum(ItemVenda.quantidade)).join(Venda).filter(ItemVenda.produto_id == produto_id, Venda.status != 'Cancelada').scalar() or 0
    saldo_a_classificar = max(0, saldo_a_classificar - total_saidas)
    saldo_real = sum(i.quantidade for i in estoque_atual) - total_saidas
    
    # Embalagens: Busca todas as embalagens individuais, mas o template filtra as vendidas
    embalagens_todos = ItemEstoque.query.filter_by(
        tipo_item="municao", 
        produto_id=produto_id
    ).filter(ItemEstoque.numero_embalagem != None, ItemEstoque.numero_embalagem != 'ATACADO').order_by(ItemEstoque.data_entrada.desc()).all()


    # 2. Histórico Limpo (Entradas via Compra vs Saídas via Venda)
    entradas_raw = db.session.query(
        CompraNF.data_emissao, CompraNF.numero, CompraItem.quantidade, CompraNF.fornecedor, CompraNF.id.label('nf_id')
    ).join(CompraItem).filter(CompraItem.produto_id == produto_id).all()

    saidas_raw = db.session.query(
        Venda.data_abertura, Venda.id.label('venda_id'), ItemVenda.quantidade, func.coalesce(Cliente.nome, Venda.cliente_nome, 'Cliente não id.').label('cliente_nome')
    ).join(ItemVenda).outerjoin(Cliente, Venda.cliente_id == Cliente.id).filter(ItemVenda.produto_id == produto_id, Venda.status != 'Cancelada').all()


    historico = []
    
    for data_mov, doc, qtd, info, nf_id in entradas_raw:
        dt = datetime.combine(data_mov, time.min) if isinstance(data_mov, date) and not isinstance(data_mov, datetime) else data_mov
        historico.append({'data': dt, 'tipo': 'entrada', 'qtd': int(qtd or 0), 'doc': doc, 'link_id': nf_id, 'info': info})

    for data_mov, venda_id, qtd, info in saidas_raw:
        dt = datetime.combine(data_mov, time.min) if isinstance(data_mov, date) and not isinstance(data_mov, datetime) else data_mov
        historico.append({'data': dt, 'tipo': 'saida', 'qtd': int(qtd or 0), 'doc': venda_id, 'link_id': venda_id, 'info': info})

    historico.sort(key=lambda x: x['data'] or datetime.min, reverse=True)

    return render_template(
        "estoque/municoes/gerenciar.html",
        produto=produto,
        embalagens=embalagens_todos, # Manda todas, o template filtra por 'disponivel'
        saldo_a_classificar=saldo_a_classificar,
        saldo_real=saldo_real,
        historico=historico
    )


# ==========================================================
# AÇÃO: REGISTRAR EMBALAGEM (Criação em Massa)
# ==========================================================
@estoque_bp.route("/municoes/registrar_embalagem", methods=["POST"])
@login_required
def municoes_registrar_embalagem():
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        packages_data = data.get('packages', [])

        if not packages_data:
            return jsonify(success=False, message="Nenhuma embalagem foi especificada."), 400

        total_necessario = sum(int(p.get('quantidade', 0)) for p in packages_data)
        
        # 1. Consome do Estoque Atacado (Pai)
        itens_atacado = ItemEstoque.query.filter_by(
            produto_id=produto_id, tipo_item="municao", status="disponivel"
        ).filter((ItemEstoque.numero_embalagem == None) | (ItemEstoque.numero_embalagem == 'ATACADO')).all()

        saldo_disponivel = sum(i.quantidade for i in itens_atacado)
        
        if saldo_disponivel < total_necessario:
            return jsonify(success=False, message=f"Saldo insuficiente ({saldo_disponivel} disp) para classificar {total_necessario} unidades."), 400

        qtd_a_remover = total_necessario
        meta_pai = {}
        
        for item in itens_atacado:
            if not meta_pai:
                meta_pai = {
                    'nf': item.nota_fiscal, 'fornecedor': item.fornecedor_id, 'compra_item': item.compra_item_id,
                    'data': item.data_entrada, 'guia': item.guia_transito_file, 'selo': item.numero_selo
                }

            if item.quantidade > qtd_a_remover:
                item.quantidade -= qtd_a_remover
                qtd_a_remover = 0
            else:
                qtd_a_remover -= item.quantidade
                db.session.delete(item)
            
            if qtd_a_remover == 0: break


        # 3. Cria as Múltiplas Caixas Individuais
        for pkg in packages_data:
            db.session.add(ItemEstoque(
                produto_id=produto_id,
                tipo_item="municao",
                numero_embalagem=pkg['embalagem'],
                lote=pkg['lote'],
                quantidade=int(pkg['quantidade']),
                status="disponivel",
                observacoes="Classificado em Lote",
                nota_fiscal=meta_pai.get('nf'),
                fornecedor_id=meta_pai.get('fornecedor'),
                data_entrada=meta_pai.get('data'),
                guia_transito_file=meta_pai.get('guia'),
                numero_selo=meta_pai.get('selo')
            ))
        
        db.session.commit()
        return jsonify(success=True)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
        
# (Rotas auxiliares mantidas)
@estoque_bp.route("/municoes/<int:item_id>/excluir", methods=["POST"])
@login_required
def municoes_excluir(item_id):
    item = ItemEstoque.query.get_or_404(item_id)
    if item.status == 'vendida':
        flash("⚠️ Item vendido não pode ser excluído.", "warning")
    else:
        db.session.delete(item)
        db.session.commit()
        flash("Item excluído.", "success")
    return redirect(url_for("estoque.municoes_gerenciar_produto", produto_id=item.produto_id))
    
@estoque_bp.route("/municoes/novo", methods=["GET", "POST"])
@estoque_bp.route("/municoes/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def municoes_gerenciar(item_id=None):
    return redirect(url_for("estoque.municoes_listar"))