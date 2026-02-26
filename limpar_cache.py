# Crie um arquivo limpar_cache.py
from app import create_app
from app.loja.routes import cache

app = create_app()
with app.app_context():
    cache.clear()
    print("🧹 Cache do sistema limpo com sucesso!")