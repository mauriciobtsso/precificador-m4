from flask import render_template
from flask_login import login_required
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque

@estoque_bp.route('/', endpoint='index')
@login_required
def index():
    totais = {
        'armas': ItemEstoque.query.filter_by(tipo='arma').count(),
        'municoes': ItemEstoque.query.filter_by(tipo='municao').count(),
        'pces': ItemEstoque.query.filter_by(tipo='pce').count(),
        'outros': ItemEstoque.query.filter_by(tipo='nao_controlado').count(),
    }
    return render_template('estoque/index.html', totais=totais)
