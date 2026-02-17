from flask import Blueprint

# Definimos o blueprint com o prefixo /loja
loja_bp = Blueprint('loja', __name__, template_folder='templates', url_prefix='/loja')

from app.loja import routes