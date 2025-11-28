# ======================
# MÓDULO: PRODUTOS
# ======================

from flask import Blueprint

# Cria o blueprint principal
produtos_bp = Blueprint(
    "produtos",
    __name__,
    url_prefix="/produtos",
    template_folder="templates",
    static_folder="static"
)

# ======================================================
# Importação segura
# ======================================================
def importar_modulo(nome):
    try:
        __import__(f"app.produtos.routes.{nome}")
    except Exception as e:
        print(f"[M4:PRODUTOS] Falha ao importar '{nome}': {e}")
        pass

# Lista de submódulos (A ORDEM IMPORTA)
submodulos = [
    "main",
    "fotos",
    "historico",
    "autosave",
    "tecnicos",
    "configs",
    "importar",
    "api"  # <--- VITAL: Registra a rota de busca
]

for nome in submodulos:
    importar_modulo(nome)