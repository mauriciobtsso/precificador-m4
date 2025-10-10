# app/uploads/ocr.py
import io
import logging
import os
from typing import Optional

from PIL import Image
import pytesseract

# Tesseract opcional (Windows): se precisar, descomente e ajuste o caminho
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def _ocr_imagem(file_bytes: bytes, lang: str = "por") -> str:
    img = Image.open(io.BytesIO(file_bytes))
    texto = pytesseract.image_to_string(img, lang=lang)
    return (texto or "").replace("\x0c", "").strip()

def _pdf_texto_pdfminer(file_bytes: bytes) -> str:
    # Evita depender de poppler. Tenta extrair texto da camada “texto” do PDF.
    from pdfminer.high_level import extract_text
    texto = extract_text(io.BytesIO(file_bytes)) or ""
    return texto.replace("\x0c", "").strip()

def _pdf_texto_por_ocr(file_bytes: bytes, lang: str = "por") -> str:
    # Fallback opcional via OCR (requer poppler instalado se usar pdf2image)
    from pdf2image import convert_from_bytes

    # Em Windows, se necessário, indique o caminho do poppler:
    poppler_path = os.getenv("POPPLER_PATH")  # ex.: r"C:\poppler-23.08.0\Library\bin"
    imgs = convert_from_bytes(file_bytes, poppler_path=poppler_path) if poppler_path else convert_from_bytes(file_bytes)

    partes = []
    for img in imgs:
        partes.append(pytesseract.image_to_string(img, lang=lang))
    return ("\n".join(partes)).replace("\x0c", "").strip()

def extrair_texto(file_bytes: bytes, filename: Optional[str] = None, lang: str = "por") -> str:
    """
    Extrai texto de imagem ou PDF com estratégia resiliente:
    - Imagem: OCR direto (pytesseract)
    - PDF: 1) pdfminer (sem poppler)  2) fallback OCR (pdf2image + tesseract)
    """
    logger = logging.getLogger("app")
    nome = (filename or "").lower()
    logger.info(f"[OCR] Iniciando OCR ({nome or 'sem-nome'})")

    try:
        if nome.endswith(".pdf"):
            logger.info("[OCR] PDF detectado -> tentando camada de texto (pdfminer)...")
            try:
                texto = _pdf_texto_pdfminer(file_bytes)
                if texto.strip():
                    logger.info("[OCR] PDF extraído via pdfminer (sem OCR).")
                    return texto
                logger.info("[OCR] PDF sem texto visível -> fallback OCR (pdf2image).")
            except Exception as e:
                logger.warning(f"[OCR] Falha pdfminer ({e}) -> fallback OCR (pdf2image).")

            # Fallback OCR em PDF
            texto = _pdf_texto_por_ocr(file_bytes, lang=lang)
            logger.info("[OCR] PDF extraído via OCR.")
            return texto

        # Caso geral: imagem
        logger.info("[OCR] Imagem detectada -> OCR com pytesseract.")
        return _ocr_imagem(file_bytes, lang=lang)

    except Exception as e:
        logger.error(f"[OCR] Erro ao extrair texto: {e}", exc_info=True)
        raise
