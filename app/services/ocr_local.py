# app/services/ocr_local.py
# -*- coding: utf-8 -*-
"""
OCR Local para o Precificador M4
--------------------------------
Fluxo:
1) Se PDF: tenta extrair texto embutido (pdfplumber).
   - Se pouco texto, rasteriza com pdf2image e roda pytesseract.
2) Se imagem: processa direto no pytesseract (com pré-processamento).
3) Corrige orientação por página (OSD), quando possível.
4) Retorna um dicionário padronizado com textos por página e metadados.

Requisitos de sistema (zero custo):
- Tesseract OCR instalado no sistema (ex.: Windows: choco install tesseract; Linux: apt-get install tesseract-ocr)
- Poppler instalado para pdf2image (ex.: Windows: choco install poppler; Linux: apt-get install poppler-utils)

Dependências Python (requirements.txt):
- pillow
- pytesseract
- pdfplumber
- pdf2image

Config via ambiente (opcional):
- POPPLER_PATH=/caminho/para/bin (no Windows pode ser necessário)
- TESSERACT_CMD=/caminho/para/tesseract.exe (se pytesseract não localizar automaticamente)

Interface de uso típica nas rotas:
----------------------------------
from app.services.ocr_local import extract_text_local

result = extract_text_local(
    file_bytes=arquivo.read(),
    filename=arquivo.filename,
    lang="por+eng",              # recomendado para BR
    dpi=300,
    max_pages=20,
    compute_confidence=False     # True calcula média de confiança (mais lento)
)
# result["texts"] -> lista de textos por página
# passe o texto para o parser inteligente (app/uploads/parsers.py) na etapa seguinte
"""

from __future__ import annotations

import io
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

from PIL import Image, ImageOps, ImageFilter, ImageSequence
import pytesseract

# pdfplumber e pdf2image podem ser opcionais em ambiente de dev sem poppler
try:
    import pdfplumber  # type: ignore
except Exception:
    pdfplumber = None  # type: ignore

try:
    from pdf2image import convert_from_bytes  # type: ignore
except Exception:
    convert_from_bytes = None  # type: ignore


logger = logging.getLogger(__name__)


# ======================
# Helpers de detecção
# ======================

def _looks_like_pdf(header: bytes, filename: str) -> bool:
    if filename and filename.lower().endswith(".pdf"):
        return True
    return header[:4] == b"%PDF"


def _safe_get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return os.environ.get(name, default)
    except Exception:
        return default


# ======================
# Pré-processamento
# ======================

def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    Pipeline leve e rápido, sem OpenCV:
    - Converte para escala de cinza
    - Autocontraste
    - Sharpen suave
    - Binarização simples (threshold adaptado pela mediana)
    """
    try:
        # Garantir modo adequado
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")

        # Se RGB, passa para L
        if img.mode == "RGB":
            img = ImageOps.grayscale(img)

        # Autocontrast ajuda muito em scans lavados
        img = ImageOps.autocontrast(img)

        # Sharpen suave para definir bordas de caracteres
        img = img.filter(ImageFilter.SHARPEN)

        # Binarização: threshold pela mediana
        # Evita depender de numpy; usa histograma do PIL
        hist = img.histogram()
        total = sum(hist)
        cum = 0
        median_gray = 0
        for i, count in enumerate(hist):
            cum += count
            if cum >= total / 2:
                median_gray = i
                break

        threshold = max(60, min(200, median_gray))  # clamp
        img = img.point(lambda x: 255 if x > threshold else 0, mode="1")

        # Volta para L (muitos perfis do tesseract trabalham melhor em L do que em 1-bit)
        img = img.convert("L")

        return img
    except Exception as e:
        logger.warning(f"Falha no pré-processamento: {e}")
        return img


# ======================
# Correção de orientação (OSD)
# ======================

def _fix_orientation(img: Image.Image) -> Image.Image:
    """
    Usa OSD do Tesseract para detectar ângulo e rotacionar se necessário.
    Silencioso em caso de falha.
    """
    try:
        osd = pytesseract.image_to_osd(img)
        # Exemplo de saída OSD inclui "Rotate: 90"
        angle = 0
        for line in osd.splitlines():
            if "Rotate:" in line:
                try:
                    angle = int(line.split(":")[1].strip())
                except Exception:
                    angle = 0
                break

        if angle and angle in (90, 180, 270):
            img = img.rotate(-angle, expand=True)  # tesseract define sentido horário
        return img
    except Exception:
        # Sem OSD ou falha: segue imagem como está
        return img


# ======================
# OCR com pytesseract
# ======================

def _ocr_image(
    img: Image.Image,
    lang: str = "por+eng",
    psm: int = 6,
    oem: int = 3,
    compute_confidence: bool = False,
) -> Tuple[str, Optional[float]]:
    """
    Roda o OCR em uma imagem PIL.
    Retorna (texto, média_confiança|None)
    """
    # Corrige orientação antes do OCR
    img = _fix_orientation(img)
    img = _preprocess_image(img)

    config = f"--psm {psm} --oem {oem}"
    try:
        if compute_confidence:
            data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
            text = " ".join([w for w in data.get("text", []) if w and w.strip() != ""])
            confs = [float(c) for c in data.get("conf", []) if c not in (-1, "-1", "", None)]
            avg_conf = round(sum(confs) / len(confs), 2) if confs else None
            return text.strip(), avg_conf
        else:
            text = pytesseract.image_to_string(img, lang=lang, config=config)
            return text.strip(), None
    except Exception as e:
        logger.error(f"Erro no pytesseract: {e}")
        return "", None


# ======================
# PDF: texto embutido
# ======================

def _pdf_textlayer_extract(file_bytes: bytes) -> List[str]:
    """
    Extrai texto embutido por página com pdfplumber.
    Se pdfplumber não estiver disponível, retorna lista vazia.
    """
    results: List[str] = []
    if not pdfplumber:
        return results

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                results.append(txt.strip())
    except Exception as e:
        logger.warning(f"Falha ao extrair texto embutido com pdfplumber: {e}")

    return results


# ======================
# PDF: rasterização
# ======================

def _pdf_to_images(
    file_bytes: bytes,
    dpi: int = 300,
    first_page: Optional[int] = None,
    last_page: Optional[int] = None,
) -> List[Image.Image]:
    """
    Converte PDF -> lista de imagens PIL por página.
    Requer pdf2image + Poppler disponíveis.
    """
    if not convert_from_bytes:
        logger.warning("pdf2image não disponível. Defina Poppler e instale pdf2image para rasterizar PDFs.")
        return []

    poppler_path = _safe_get_env("POPPLER_PATH")
    try:
        images = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            first_page=first_page,
            last_page=last_page,
            poppler_path=poppler_path,
            fmt="png",
            thread_count=2
        )
        return images or []
    except Exception as e:
        logger.error(f"Falha ao rasterizar PDF: {e}")
        return []


# ======================
# Imagens multi-frame (ex.: TIFF)
# ======================

def _image_bytes_to_frames(file_bytes: bytes) -> List[Image.Image]:
    """
    Lê bytes de imagem (JPG/PNG/TIFF) e retorna frames (páginas).
    """
    frames: List[Image.Image] = []
    try:
        im = Image.open(io.BytesIO(file_bytes))
        # Alguns formatos têm múltiplos frames (TIFF)
        for frame in ImageSequence.Iterator(im):
            frames.append(frame.copy())
        if not frames:
            frames = [im]
    except Exception as e:
        logger.error(f"Falha ao abrir imagem: {e}")
    return frames


# ======================
# Função pública principal
# ======================

def extract_text_local(
    file_bytes: bytes,
    filename: str,
    lang: str = "por+eng",
    dpi: int = 300,
    max_pages: int = 20,
    try_pdf_textlayer: bool = True,
    compute_confidence: bool = False,
) -> Dict[str, Any]:
    """
    Executa OCR local em PDF ou imagem e retorna um dicionário padronizado:

    {
      "engine": "local",
      "filename": "arquivo.pdf",
      "filetype": "pdf" | "image",
      "pages": 3,
      "texts": ["texto p1", "texto p2", "texto p3"],
      "avg_confidence": 88.5 | None,
      "used_pdf_textlayer": true|false,
      "meta": {
         "truncated": false,
         "pdf_textlayer_score": 0.87
      }
    }

    Notas:
    - Se texto embutido do PDF for consistente, evitamos rasterização (mais rápido).
    - Se vier pouco texto (score baixo), caímos para rasterização + pytesseract.
    """

    if not file_bytes:
        raise ValueError("file_bytes não pode ser vazio.")

    header = file_bytes[:8]
    is_pdf = _looks_like_pdf(header, filename or "")

    result: Dict[str, Any] = {
        "engine": "local",
        "filename": filename,
        "filetype": "pdf" if is_pdf else "image",
        "pages": 0,
        "texts": [],
        "avg_confidence": None,
        "used_pdf_textlayer": False,
        "meta": {
            "truncated": False,
            "pdf_textlayer_score": None,
        }
    }

    # ======================
    # Caso PDF
    # ======================
    if is_pdf:
        texts_embedded: List[str] = []
        if try_pdf_textlayer and pdfplumber:
            texts_embedded = _pdf_textlayer_extract(file_bytes)
            # score simples: proporção de páginas com >= 30 chars
            if texts_embedded:
                rich_pages = sum(1 for t in texts_embedded if len((t or "").strip()) >= 30)
                score = round(rich_pages / max(1, len(texts_embedded)), 4)
                result["meta"]["pdf_textlayer_score"] = score

        # Critério: se score >= 0.6, já aceitável; senão, rasteriza
        if texts_embedded and (result["meta"]["pdf_textlayer_score"] or 0) >= 0.6:
            result["used_pdf_textlayer"] = True
            # Limitar páginas se exceder max_pages
            if len(texts_embedded) > max_pages:
                texts_embedded = texts_embedded[:max_pages]
                result["meta"]["truncated"] = True
            result["texts"] = texts_embedded
            result["pages"] = len(texts_embedded)
            return result

        # Rasterização (OCR)
        images = _pdf_to_images(file_bytes, dpi=dpi)
        if not images:
            # Se falhou rasterizar, mas havia algum texto embutido, retorna-o
            if texts_embedded:
                result["used_pdf_textlayer"] = True
                if len(texts_embedded) > max_pages:
                    texts_embedded = texts_embedded[:max_pages]
                    result["meta"]["truncated"] = True
                result["texts"] = texts_embedded
                result["pages"] = len(texts_embedded)
                return result
            # Sem saída viável
            return result

        if len(images) > max_pages:
            images = images[:max_pages]
            result["meta"]["truncated"] = True

        page_texts: List[str] = []
        confs: List[float] = []

        for img in images:
            text, conf = _ocr_image(
                img, lang=lang, psm=6, oem=3, compute_confidence=compute_confidence
            )
            page_texts.append(text)
            if conf is not None:
                confs.append(conf)

        result["texts"] = page_texts
        result["pages"] = len(page_texts)
        if confs:
            result["avg_confidence"] = round(sum(confs) / len(confs), 2)

        return result

    # ======================
    # Caso Imagem
    # ======================
    frames = _image_bytes_to_frames(file_bytes)
    if not frames:
        return result

    if len(frames) > max_pages:
        frames = frames[:max_pages]
        result["meta"]["truncated"] = True

    page_texts = []
    confs: List[float] = []

    for frame in frames:
        # Opcional: normalizar para ~300DPI (quando metadados de DPI estiverem muito baixos)
        try:
            xdpi, ydpi = frame.info.get("dpi", (dpi, dpi))
        except Exception:
            xdpi, ydpi = (dpi, dpi)

        # Upscale leve quando DPI < 200 melhora legibilidade do OCR
        if min(xdpi, ydpi) < 200:
            scale = 300.0 / max(1, min(xdpi, ydpi))
            new_size = (int(frame.width * scale), int(frame.height * scale))
            frame = frame.resize(new_size, Image.LANCZOS)

        text, conf = _ocr_image(
            frame, lang=lang, psm=6, oem=3, compute_confidence=compute_confidence
        )
        page_texts.append(text)
        if conf is not None:
            confs.append(conf)

    result["texts"] = page_texts
    result["pages"] = len(page_texts)
    if confs:
        result["avg_confidence"] = round(sum(confs) / len(confs), 2)

    return result


# ======================
# Execução direta (teste rápido)
# ======================

if __name__ == "__main__":
    # Pequeno teste manual: leia um arquivo local e imprima um resumo
    # Uso:
    #   python app/services/ocr_local.py caminho/arquivo.pdf
    import sys
    import json
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Uso: python app/services/ocr_local.py <caminho_arquivo>")
        sys.exit(1)

    p = sys.argv[1]
    with open(p, "rb") as f:
        fb = f.read()

    res = extract_text_local(
        file_bytes=fb,
        filename=os.path.basename(p),
        lang="por+eng",
        dpi=300,
        max_pages=10,
        try_pdf_textlayer=True,
        compute_confidence=True,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
