import os
import csv
from datetime import datetime
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

def fazer_backup():
    with app.app_context():
        # Cria uma pasta para o backup com a data de hoje
        data_hoje = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        pasta_backup = f'backup_{data_hoje}'
        
        if not os.path.exists(pasta_backup):
            os.makedirs(pasta_backup)
            
        inspector = inspect(db.engine)
        tabelas = inspector.get_table_names()
        
        print(f"📂 Iniciando backup de {len(tabelas)} tabelas...")

        for tabela in tabelas:
            try:
                # Consulta todos os dados da tabela
                result = db.session.execute(text(f"SELECT * FROM {tabela}"))
                colunas = result.keys()
                rows = result.fetchall()

                arquivo_csv = os.path.join(pasta_backup, f"{tabela}.csv")
                
                with open(arquivo_csv, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(colunas) # Cabeçalho
                    writer.writerows(rows)   # Dados
                
                print(f"✅ Tabela [{tabela}] salva com sucesso.")
            except Exception as e:
                print(f"❌ Erro na tabela [{tabela}]: {e}")

        print(f"\n✨ Backup concluído! Os arquivos estão na pasta: {pasta_backup}")

if __name__ == "__main__":
    fazer_backup()