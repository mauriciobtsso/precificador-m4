import os
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")