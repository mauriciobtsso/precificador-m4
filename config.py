import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

class Config:
    # Segurança
    SECRET_KEY = os.getenv("SECRET_KEY", "m4-tatica-secret")

    # Banco
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # OCR portátil
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")

    # Cloudflare R2 (aliases amigáveis para o código)
    R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
    R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET = os.getenv("R2_BUCKET_NAME")
