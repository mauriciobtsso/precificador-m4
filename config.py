import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "m4-tatica-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # OCR
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")

    # Cloudflare R2
    R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
    R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET = os.getenv("R2_BUCKET_NAME")

    # Timezone global
    TIMEZONE = "America/Fortaleza"

    # SQLAlchemy — Proteção total contra instabilidades SSL (Locaweb)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,          # testa conexão antes de usar
        "pool_recycle": 1800,           # recicla conexões a cada 30 min
        "connect_args": {
            "options": "-c timezone=America/Fortaleza",
            "sslmode": "require",       # força SSL seguro
            "connect_timeout": 10       # evita travas longas
        }
    }
