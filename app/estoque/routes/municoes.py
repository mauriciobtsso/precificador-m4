from flask import render_template, request
from flask_login import login_required
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque

@estoque_bp.route('/municoes', endpoint='municoes_listar')
@login_required
def listar_municoes():
    lote = (request.args.get('lote') or '').strip()
    embalagem = (request.args.get('embalagem') or '').strip()
    query = ItemEstoque.query.filter_by(tipo='municao')
    if lote:
        query = query.filter(ItemEstoque.lote.ilike(f"%{lote}%"))
    if embalagem:
        query = query.filter(ItemEstoque.numero_embalagem.ilike(f"%{embalagem}%"))
    municoes = query.order_by(ItemEstoque.data_recebimento.desc()).all()
    return render_template('estoque/municoes_listar.html', municoes=municoes)
