# Mantém o pacote organizado para rotas do módulo Clientes

from app.clientes import clientes_bp
from app.clientes.routes import loja_acesso

# Importa todos os submódulos de rota para registrar as URLs
from . import base
from . import enderecos
from . import contatos
from . import documentos
from . import armas
from . import processos
from . import comunicacoes
from . import api
