from flask import render_template, request
from flask_login import login_required
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque

@estoque_bp.route('/pces', endpoint='pces_listar')
@login_required
def listar_pces():
    termo = (request.args.get('termo') or '').strip()
    query = ItemEstoque.query.filter_by(tipo='pce')
    if termo:
        query = query.filter(ItemEstoque.numero_serie.ilike(f"%{termo}%") | ItemEstoque.lote.ilike(f"%{termo}%"))
    items = query.order_by(ItemEstoque.data_recebimento.desc()).all()
    return render_template('estoque/pces_listar.html', items=items)
