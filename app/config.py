from flask import current_app

import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")

# Carregar variáveis do .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = UPLOAD_FOLDER

def get_config(key: str, default=None):
    """
    Helper para acessar configs da aplicação de forma segura.
    Exemplo: get_config("whatsapp_prefixo", "")
    """
    return current_app.config.get(key, default)