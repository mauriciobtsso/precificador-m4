from flask import render_template, request
from flask_login import login_required
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque

@estoque_bp.route('/nao-controlados', endpoint='nao_controlados_listar')
@login_required
def listar_nao_controlados():
    termo = (request.args.get('termo') or '').strip()
    query = ItemEstoque.query.filter_by(tipo='nao_controlado')
    if termo:
        query = query.filter(ItemEstoque.lote.ilike(f"%{termo}%") | ItemEstoque.numero_embalagem.ilike(f"%{termo}%"))
    items = query.order_by(ItemEstoque.data_recebimento.desc()).all()
    return render_template('estoque/nao_controlados_listar.html', items=items)
