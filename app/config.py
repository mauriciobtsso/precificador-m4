from flask import current_app
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")

# Carregar variáveis do .env
load_dotenv()

class Config:
    # ====================================================
    # SEGURANÇA: SECRET_KEY OBRIGATÓRIA
    # ====================================================
    # Tenta pegar do ambiente.
    SECRET_KEY = os.getenv("SECRET_KEY")
    
    # Verifica se estamos rodando localmente (desenvolvimento)
    _is_dev = os.getenv("FLASK_ENV") == "development" or os.getenv("FLASK_DEBUG") == "1"

    if not SECRET_KEY:
        if _is_dev:
            # Apenas localmente aceitamos uma chave fraca para facilitar testes
            SECRET_KEY = "dev_key_apenas_para_testes_locais"
            print("⚠️ AVISO: Usando SECRET_KEY de desenvolvimento. Não use em produção!")
        else:
            # Em produção, o sistema DEVE falhar se não tiver chave segura
            raise ValueError("❌ ERRO CRÍTICO DE SEGURANÇA: A variável de ambiente 'SECRET_KEY' não foi configurada!")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = UPLOAD_FOLDER

def get_config(key: str, default=None):
    """
    Helper para acessar configs da aplicação de forma segura.
    Exemplo: get_config("whatsapp_prefixo", "")
    """
    return current_app.config.get(key, default)