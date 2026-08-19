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
    # 4️⃣ Parsing inteligente pós-IA / Fallback Local
    # ==========================================
    try:
        from app.uploads.parsers import parse_craf, parse_cr, parse_cnh, parse_rg

        # Se a IA falhou (retornou erro 404/401 nas observações), forçamos o fallback local
        ia_falhou = "Erro no processamento via Groq" in (resultado_ia.get("observacoes") or "")
        
        # Normaliza categoria
        categoria = (resultado_ia.get("categoria") or "").upper().strip()
        
        # Se a IA falhou, tentamos detectar a categoria pelo texto bruto
        if ia_falhou or categoria == "OUTRO":
            txt_upper = texto_final.upper()
            if "CERTIFICADO DE REGISTRO" in txt_upper and "ARMA DE FOGO" in txt_upper:
                categoria = "CRAF"
            elif "CERTIFICADO DE REGISTRO" in txt_upper and "EXÉRCITO" in txt_upper:
                categoria = "CR"
            elif "CARTEIRA NACIONAL DE HABILITAÇÃO" in txt_upper or "CNH" in txt_upper:
                categoria = "CNH"
            elif "REGISTRO GERAL" in txt_upper or "IDENTIDADE" in txt_upper:
                categoria = "RG"
        
        # Mapeia campos do LLM para o formato esperado pelos formulários (se IA retornou algo)
        if resultado_ia.get("tipo_arma"): resultado_ia["tipo"] = resultado_ia["tipo_arma"]
        if resultado_ia.get("marca_arma"): resultado_ia["marca"] = resultado_ia["marca_arma"]
        if resultado_ia.get("modelo_arma"): resultado_ia["modelo"] = resultado_ia["modelo_arma"]
        if resultado_ia.get("serie_arma"): resultado_ia["numero_serie"] = resultado_ia["serie_arma"]
        if resultado_ia.get("numero_documento") and categoria == "CRAF": 
            resultado_ia["numero_sigma"] = resultado_ia["numero_documento"]
        
        # Aplica parsers dedicados baseados na categoria detectada (Reforço com Regex)
        if categoria == "CRAF":
            parsed = parse_craf(texto_final)
            # IA tem prioridade em campos complexos, Regex em campos estruturados
            for k, v in parsed.items():
                if not resultado_ia.get(k) or k in ["numero_sigma", "numero_serie"]:
                    resultado_ia[k] = v
            resultado_ia["categoria"] = "CRAF"
        elif categoria == "CR":
            parsed = parse_cr(texto_final)
            for k, v in parsed.items():
                if not resultado_ia.get(k) or k == "numero_cr":
                    resultado_ia[k] = v
            resultado_ia["categoria"] = "CR"
        elif categoria == "CNH":
            parsed = parse_cnh(texto_final)
            for k, v in parsed.items():
                if not resultado_ia.get(k) or k == "registro":
                    resultado_ia[k] = v
            resultado_ia["categoria"] = "CNH"
        elif categoria == "RG":
            parsed = parse_rg(texto_final)
            for k, v in parsed.items():
                if not resultado_ia.get(k) or k == "rg_numero":
                    resultado_ia[k] = v
            resultado_ia["categoria"] = "RG"

    except Exception as e:
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
