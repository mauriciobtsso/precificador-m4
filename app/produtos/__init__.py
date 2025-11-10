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
# Importação segura e com log individual
# ======================================================
def importar_modulo(nome):
    """Importa submódulos e mostra log claro no console."""
    try:
        __import__(f"app.produtos.routes.{nome}")
        # print(f"[M4:PRODUTOS] ✅ Rotas '{nome}' carregadas.")
    except Exception as e:
        print(f"[M4:PRODUTOS] Falha ao importar '{nome}': {e}")
        pass


# Lista dos submódulos ativos do pacote
submodulos = [
    "main",
    "fotos",
    "historico",
    "autosave",
    "tecnicos",
    "configs",
    "importar",  # 🚀 Importação CSV de produtos
]

for nome in submodulos:
    importar_modulo(nome)
