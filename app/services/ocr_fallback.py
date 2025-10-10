# app/services/ocr_fallback.py
# -*- coding: utf-8 -*-
"""
OCR Fallback (OCR.Space) – versão otimizada
-------------------------------------------
Converte PDFs grandes para imagem e envia apenas a primeira página,
reduzindo o tempo de resposta e evitando timeout.
"""

import os
import io
import requests
import logging
from typing import Dict, Any
from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger(__name__)

OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "")
OCR_SPACE_URL = "https://api.ocr.space/parse/image"

def _pdf_to_image_first_page(file_bytes: bytes) -> bytes:
    """Converte a primeira página de um PDF em JPEG otimizado."""
    try:
        images = convert_from_bytes(file_bytes, dpi=200, first_page=1, last_page=1)
        img = images[0]
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Falha ao converter PDF: {e}")
        return file_bytes


def extract_text_fallback(file_bytes: bytes, filename: str = "documento.pdf", language: str = "por") -> Dict[str, Any]:
    if not OCR_SPACE_API_KEY:
        return {"engine": "ocr.space", "texts": [], "error": "OCR_SPACE_API_KEY não configurada"}

    # Se for PDF, converte a primeira página para JPEG
    if filename.lower().endswith(".pdf"):
        file_bytes = _pdf_to_image_first_page(file_bytes)
        filename = filename.replace(".pdf", ".jpg")

    try:
        files = {"file": (filename, file_bytes)}
        data = {
            "apikey": OCR_SPACE_API_KEY,
            "language": language,
            "isOverlayRequired": False,
            "OCREngine": 2,
        }

        resp = requests.post(OCR_SPACE_URL, files=files, data=data, timeout=180)
        if resp.status_code != 200:
            return {"engine": "ocr.space", "texts": [], "error": f"HTTP {resp.status_code}"}

        result = resp.json()
        texts = [p.get("ParsedText", "").strip() for p in result.get("ParsedResults", []) if p.get("ParsedText")]
        if not texts:
            return {"engine": "ocr.space", "texts": [], "error": "Nenhum texto retornado"}

        return {"engine": "ocr.space", "texts": texts, "error": None}

    except requests.exceptions.Timeout:
        return {"engine": "ocr.space", "texts": [], "error": "timeout na API OCR.Space"}
    except Exception as e:
        logger.exception("Erro no OCR.Space")
        return {"engine": "ocr.space", "texts": [], "error": str(e)}


if __name__ == "__main__":
    import json
    caminho = input("Caminho do arquivo de teste: ").strip()
    with open(caminho, "rb") as f:
        fb = f.read()

    resultado = extract_text_fallback(fb, filename=caminho)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
