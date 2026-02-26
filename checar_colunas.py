from app import create_app, db
from sqlalchemy import inspect

app = create_app()

def checar_banco():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Tabelas que precisamos verificar
        alvos = ['produtos', 'banners', 'marca_produto', 'categoria_produto']
        
        print("🕵️ Investigando nomes das colunas...")
        for tabela in alvos:
            if tabela in inspector.get_table_names():
                colunas = [c['name'] for c in inspector.get_columns(tabela)]
                print(f"\n📌 Tabela: {tabela}")
                print(f"   Colunas: {', '.join(colunas)}")
            else:
                print(f"\n⚠️ Tabela '{tabela}' não encontrada.")

if __name__ == "__main__":
    checar_banco()