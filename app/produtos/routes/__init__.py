from flask import Blueprint

# Blueprint principal
from app.produtos import produtos_bp

# Importa todos os submódulos de rotas
# A ordem não importa muito, mas é essencial importar TODOS
from .main import *
from .fotos import *
from .historico import *
from .autosave import *
from .tecnicos import *
from .configs import *
from .utils import *
from .importar import *
from .api import * # <--- ESTA LINHA ESTAVA FALTANDO