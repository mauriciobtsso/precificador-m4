# ======================================================
# LIMPAR VENDAS E ITENS_VENDA (com path fix)
# ======================================================
import os
import sys

# Garante que a pasta raiz (precificador-m4) esteja no path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.vendas.models import Venda, ItemVenda

app = create_app()

with app.app_context():
    print("⚠️  Isso vai apagar todas as vendas e itens de venda!")
    confirm = input("Tem certeza que deseja continuar? (s/n): ").strip().lower()
    if confirm != "s":
        print("Operação cancelada.")
        sys.exit(0)

    db.session.query(ItemVenda).delete()
    db.session.query(Venda).delete()
    db.session.commit()
    print("✅ Tabelas 'vendas' e 'itens_venda' limpas com sucesso!")
