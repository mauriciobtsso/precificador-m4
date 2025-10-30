from flask import render_template, request
from flask_login import login_required
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque

@estoque_bp.route('/armas', endpoint='armas_listar')
@login_required
def listar_armas():
    termo = (request.args.get('termo') or '').strip()
    status = request.args.get('status')
    query = ItemEstoque.query.filter_by(tipo='arma')
    if termo:
        query = query.filter(
    ItemEstoque.numero_serie.ilike(f"%{termo}%") |
    ItemEstoque.numero_serie.ilike(f"%{termo}%")
)
    if status:
        query = query.filter_by(status=status)
    armas = query.order_by(ItemEstoque.data_recebimento.desc()).all()
    return render_template('estoque/armas_listar.html', armas=armas)
