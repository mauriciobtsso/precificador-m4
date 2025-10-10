import pdfplumber
import pytesseract
from PIL import Image
from io import BytesIO
from flask import current_app
import boto3

try:
    from app.uploads.ocr import extrair_texto as _ocr_extrair_texto
except Exception:
    _ocr_extrair_texto = None

def extrair_texto(file_bytes: bytes, filename: str | None = None) -> str:
    """
    Wrapper mantido para compatibilidade com rotas antigas.
    Delega para app.uploads.ocr.extrair_texto, se disponível.
    """
    if _ocr_extrair_texto is None:
        raise RuntimeError("OCR não configurado: app.uploads.ocr.extrair_texto indisponível.")
    return _ocr_extrair_texto(file_bytes, filename)

# ======================
# STORAGE (R2)
# ======================
def get_s3():
    """Cria cliente S3 usando as configs do Flask."""
    return boto3.client(
        "s3",
        endpoint_url=current_app.config["R2_ENDPOINT"],
        aws_access_key_id=current_app.config["R2_ACCESS_KEY"],
        aws_secret_access_key=current_app.config["R2_SECRET_KEY"],
    )


def get_bucket():
    """Retorna nome do bucket configurado."""
    return current_app.config["R2_BUCKET"]


# ======================
# OCR / PDF
# ======================
def extrair_texto(file_bytes, filename):
    """Extrai texto de PDF ou imagem via OCR (pytesseract)."""
    texto = ""
    if filename.lower().endswith(".pdf"):
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            texto = "\n".join(page.extract_text() or "" for page in pdf.pages)
    else:
        pytesseract.pytesseract.tesseract_cmd = current_app.config["TESSERACT_CMD"]
        img = Image.open(BytesIO(file_bytes))
        texto = pytesseract.image_to_string(img, lang="por")
    return texto
