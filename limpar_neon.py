import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def limpar_banco():
    load_dotenv()
    url_neon = os.getenv("DATABASE_URL_NEON")
    
    if not url_neon:
        print("ERRO: DATABASE_URL_NEON não encontrada no .env")
        sys.exit(1)

    print("⚠️  ATENÇÃO: Este script vai APAGAR TODAS AS TABELAS E DADOS da NeonDB.")
    print(f"Destino: {url_neon.split('@')[1]} \n")
    
    confirmacao = input("Digite 'SIM' em maiúsculo para confirmar e prosseguir: ")
    
    if confirmacao == "SIM":
        try:
            engine = create_engine(url_neon)
            with engine.begin() as conn:
                print(">> Deletando schema public...")
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                
                print(">> Recriando schema public vazio...")
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
                
            print("\n✅ NeonDB zerada com sucesso! O quadro está em branco.")
        except Exception as e:
            print(f"\n❌ Erro ao limpar o banco: {e}")
    else:
        print("\n🚫 Operação cancelada. Ufa, nada foi apagado.")

if __name__ == "__main__":
    limpar_banco()