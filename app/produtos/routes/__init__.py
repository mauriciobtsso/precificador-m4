from flask import Blueprint

# Blueprint principal (mantém o mesmo nome e prefixo)
from app.produtos import produtos_bp

# Importa submódulos (em breve criaremos)
from .main import *
from .fotos import *
from .historico import *
from .autosave import *
from .tecnicos import *
from .configs import *
from .utils import *
from .importar import *
from .api import *
