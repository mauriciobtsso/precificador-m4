from flask import Blueprint

# Blueprint do Catálogo de Atendimento Presencial M4 Tática
# Interface otimizada para iPad Mini — sem duplicação de dados
catalogo_bp = Blueprint(
    'catalogo',
    __name__,
    template_folder='templates',
)

from app.catalogo import routes  # noqa: F401, E402
