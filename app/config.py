from flask import current_app

import os
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

def get_config(key: str, default=None):
    """
    Helper para acessar configs da aplicação de forma segura.
    Exemplo: get_config("whatsapp_prefixo", "")
    """
    return current_app.config.get(key, default)