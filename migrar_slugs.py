from app import create_app, db
from app.produtos.models import Produto
import re

def gera_slug_simples(texto):
    if not texto: return ""
    texto = texto.lower().strip()
    # Substituições básicas de acentos
    substituicoes = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
        'ã': 'a', 'õ': 'o', 'ç': 'c'
    }
    for char, replacement in substituicoes.items():
        texto = texto.replace(char, replacement)
    texto = re.sub(r'[^\w\s-]', '', texto)
    return re.sub(r'[\s_-]+', '-', texto)

app = create_app()
with app.app_context():
    print("Iniciando migração de produtos para a Loja...")
    produtos = Produto.query.all()
    
    for p in produtos:
        # Gera o slug se não existir
        if not p.slug:
            p.slug = gera_slug_simples(p.nome)
        
        # Ativa na loja por padrão (você pode desativar manualmente depois no admin)
        p.visivel_loja = True
        
        print(f"Produto atualizado: {p.nome} -> {p.slug}")
    
    db.session.commit()
    print("\nSucesso! Todos os produtos foram preparados para a nova /loja.")