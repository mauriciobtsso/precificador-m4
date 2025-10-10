# app/services/ocr_pipeline.py
# -*- coding: utf-8 -*-
"""
Pipeline OCR + IA – Precificador M4
-----------------------------------
Combina:
1️⃣ OCR Local (pytesseract / pdfplumber)
2️⃣ OCR Fallback (OCR.Space)
3️⃣ Interpretação via LLM (Groq)
4️⃣ Parsing inteligente (ex: CRAF)
"""

from app.services import ocr_local, ocr_fallback, ocr_inteligente


def processar_documento(file_bytes: bytes, filename: str) -> dict:
    """
    Faz OCR híbrido + IA e retorna JSON padronizado:
    {
      "ocr_engine": "ocr.space" | "local",
      "ia_engine": "llama-3.1-8b-instant",
      "resultado": {...}
    }
    """
    # 1️⃣ Tenta OCR local
    resultado_local = ocr_local.extract_text_local(file_bytes=file_bytes, filename=filename)
    textos_local = [t for t in resultado_local.get("texts", []) if t.strip()]

    # 2️⃣ Se o local não retornar texto, tenta OCR.Space
    if not textos_local:
        resultado_fallback = ocr_fallback.extract_text_fallback(file_bytes, filename)
        textos = [t for t in resultado_fallback.get("texts", []) if t.strip()]
        engine = resultado_fallback.get("engine", "ocr.space")
    else:
        textos = textos_local
        engine = resultado_local.get("engine", "local")

    # Caso não tenha extraído texto algum
    if not textos:
        return {
            "erro": "Nenhum texto pôde ser extraído pelo OCR",
            "ocr_engine": engine
        }

    # 3️⃣ Interpretação via IA (Groq)
    texto_final = "\n".join(textos)
    resultado_ia = ocr_inteligente.interpretar_documento(texto_final)

    # ==========================================
    # 4️⃣ Parsing inteligente pós-IA
    # ==========================================
    try:
        from app.uploads.parsers import parse_craf

        # Normaliza possíveis campos
        categoria = (resultado_ia.get("categoria") or "").upper().strip()
        texto_extraido = (
            resultado_ia.get("texto_extraido")
            or resultado_ia.get("texto")
            or texto_final
        )

        # 🔹 Aplica parser dedicado apenas se for CRAF
        if categoria == "CRAF":
            parsed = parse_craf(texto_extraido)
            # Faz merge dos dados do parser no resultado final
            resultado_ia.update(parsed)

    except Exception as e:
        # Em caso de erro no parser, mantém resultado original (nunca quebra)
        resultado_ia["parser_error"] = str(e)

    # 5️⃣ Retorno padronizado
    return {
        "ocr_engine": engine,
        "ia_engine": resultado_ia.get("engine", "groq"),
        "resultado": resultado_ia
    }


# ===========================
# Teste isolado
# ===========================
if __name__ == "__main__":
    import json
    caminho = input("Caminho do arquivo: ").strip()
    with open(caminho, "rb") as f:
        fb = f.read()
    print(json.dumps(processar_documento(fb, caminho), ensure_ascii=False, indent=2))
