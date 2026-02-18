from flask import Blueprint

loja_admin_bp = Blueprint(
    'loja_admin', 
    __name__, 
    template_folder='templates',
    static_folder='static'
)

from app.loja_admin import routes