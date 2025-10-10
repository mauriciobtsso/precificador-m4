import re
import os
import tempfile
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

# =======================================
# HELPERS
# =======================================

def _extract(pattern, texto, group=1, transform=None, flags=re.I):
    """Extrai valor por regex, aplica transform opcional e retorna string."""
    match = re.search(pattern, texto, flags)
    if match:
        val = match.group(group).strip()
        return transform(val) if transform else val
    return ""


def _norm(s: str) -> str:
    """Normaliza espaços e remove quebras de linha do OCR."""
    return re.sub(r"\s+", " ", s or "").strip()


# =======================================
# MAPAS DE NORMALIZAÇÃO
# =======================================
TIPO_MAP = {
    "PISTOLA": "pistola",
    "REVOLVER": "revolver",
    "REVÓLVER": "revolver",
    "CARABINA": "carabina_fuzil",
    "FUZIL": "carabina_fuzil",
    "ESPINGARDA": "espingarda",
    "GARRUNCHA": "garruncha",
}

FUNCIONAMENTO_MAP = {
    "REPETICAO": "repeticao",
    "REPETIÇÃO": "repeticao",
    "SEMI-AUTOMATICA": "semi_automatica",
    "SEMI AUTOMATICA": "semi_automatica",
    "SEMI-AUTOMÁTICA": "semi_automatica",
    "AUTOMATICA": "automatica",
    "AUTOMÁTICA": "automatica",
}

EMISSOR_MAP = {
    "SIGMA": "sigma",
    "SINARM-CAC": "sinarm_cac",
    "SINARM": "sinarm",
}

CATEGORIA_MAP = {
    "CIVIL": "civil",
    "ATIRADOR": "atirador",
    "COLECIONADOR": "colecionador",
    "CAC": "cac_excepcional",
    "CAÇADOR EXCEPCIONAL": "cac_excepcional",
    "CAÇADOR SUBSISTENCIA": "cac_subsistencia",
    "CAÇADOR SUBSISTÊNCIA": "cac_subsistencia",
    "POLICIAL MILITAR": "policial_militar",
    "GUARDA MUNICIPAL": "guarda_municipal",
    "INSTRUTOR POLICIA FEDERAL": "instrutor_pf",
    "INSTRUTOR POLÍCIA FEDERAL": "instrutor_pf",
    "ABIN": "abin",
    "GSI": "gsi",
    "ANALISTA TRIBUTARIO": "analista_tributario",
    "ANALISTA TRIBUTÁRIO": "analista_tributario",
    "AUDITOR FISCAL": "auditor_fiscal",
    "BOMBEIRO MILITAR": "bombeiro_militar",
    "GUARDA PORTUARIO": "guarda_portuario",
    "GUARDA PORTUÁRIO": "guarda_portuario",
    "LOJA": "loja",
    "MAGISTRADO": "magistrado",
    "MINISTERIO PUBLICO": "ministerio_publico",
    "MINISTÉRIO PÚBLICO": "ministerio_publico",
    "MILITAR FORCAS ARMADAS": "militar_forcas_armadas",
    "MILITAR FORÇAS ARMADAS": "militar_forcas_armadas",
    "POLICIAL CIVIL": "policial_civil",
    "POLICIAL CAMARA": "policial_camara",
    "POLICIAL CÂMARA": "policial_camara",
    "POLICIAL SENADO": "policial_senado",
    "POLICIAL FEDERAL": "policial_federal",
    "POLICIAL RODOVIARIO FEDERAL": "policial_rodoviario",
    "POLICIAL RODOVIÁRIO FEDERAL": "policial_rodoviario",
}

# =======================================
# PARSER CRAF / CR / CNH / RG (originais)
# =======================================

def parse_craf(texto: str) -> dict:
    """
    Parser robusto para CRAF.
    - Mantém compatibilidade com mapas externos (TIPO_MAP, FUNCIONAMENTO_MAP, EMISSOR_MAP, CATEGORIA_MAP).
    - Extrai: tipo, funcionamento, marca, modelo, calibre, numero_serie, numero_sigma, emissor_craf,
      categoria_adquirente, data_validade_craf, data_emissao_craf (opcional).
    - Usa múltiplas heurísticas/regex para localizar o número de registro (SIGMA/CRAF).
    """
    import re

    def _clean(s):
        if not s:
            return ""
        return s.strip().replace(":", "").replace(";", "").replace(".", "").upper()

    def _first_or_none(lst):
        return lst[0] if lst else None

    dados = {}
    STOP = r"(?:TIPO|MARCA|MODELO|CALIBRE|FUNCIONAMENTO|EMISSOR|N[ºo]?\s*(?:DE\s*)?S[ÉE]RIE|N[ºo]?\s+SIGMA|N[ºo]?\s+(?:REGISTRO|CRAF)|VALIDADE|CATEGORIA|DATA|EXPEDIÇÃO|\n|$)"
    txt_upper = _norm(texto).upper()

    # TIPO
    tipo_detectado = _extract(rf"\bTIPO\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", txt_upper).upper()
    if not tipo_detectado:
        m2 = re.search(r"\b(PISTOLA|REVOLVER|REVÓLVER|CARABINA|FUZIL|ESPINGARDA|GARRUNCHA)\b", txt_upper, re.I)
        tipo_detectado = m2.group(1).upper() if m2 else ""
    dados["tipo"] = TIPO_MAP.get(tipo_detectado, "")

    # FUNCIONAMENTO
    funcionamento_detectado = _extract(rf"\bFUNCIONAMENTO\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", txt_upper).upper()
    dados["funcionamento"] = ""
    for key, val in FUNCIONAMENTO_MAP.items():
        if key in funcionamento_detectado or key in txt_upper:
            dados["funcionamento"] = val
            break

    # MARCA / MODELO
    m = re.search(rf"\bMARCA\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    dados["marca"] = _norm(m.group(1)).title() if m else ""

    m = re.search(rf"\bMODELO\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    dados["modelo"] = _norm(m.group(1)).title() if m else ""

    # CALIBRE
    m = re.search(rf"\bCALIBRE\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    cal = _norm(m.group(1)) if m else ""
    cal = cal.replace("X", "x").replace("MM", "mm").replace("Mm", "mm")
    dados["calibre"] = cal

    # NÚMERO DE SÉRIE (o que está gravado na arma)
    m = re.search(rf"(?:N[ºo]?\s*(?:DE\s*)?)?S[ÉE]RIE\s*[:\-]?\s*([A-Z0-9\-]{{3,20}})\s*(?={STOP})", texto, re.I)
    if not m:
        # fallback: padrão comum de serial (letras+digitos)
        m = re.search(r"\b([A-Z]{1,4}[0-9]{3,12})\b", texto)
    dados["numero_serie"] = _clean(m.group(1)) if m else ""

    # ======================
    # NÚMERO DO REGISTRO (SIGMA / CRAF) — heurísticas avançadas
    # ======================
    # ======================
    # NÚMERO DO REGISTRO (SIGMA / CRAF) — heurísticas avançadas (revisado)
    # ======================
    numero_sigma = ""
    found_by = None

    # helper: checa se candidato é substring dos dígitos do serial
    def _is_in_serial(candidate, serial):
        if not serial or not candidate:
            return False
        # compara apenas a parte numérica do serial com o candidato
        serial_nums = re.findall(r"\d{3,}", serial)
        for s in serial_nums:
            if s and s in candidate:
                return True
        # também checa se candidate (numérico) está contido no serial inteiro
        return candidate in serial

    serial_val = dados.get("numero_serie") or ""

    # 1) Padrões explícitos: "Nº SIGMA", "Nº REGISTRO", "Nº CRAF", "REGISTRO: 2207509"
    patterns = [
        r"(?:N[ºo]?\s*(?:DE\s*)?)SIGMA\s*[:\-]?\s*([0-9A-Z\/\-]{3,20})",
        r"(?:N[ºo]?\s*(?:DE\s*)?)CRAF\s*[:\-]?\s*([0-9A-Z\/\-]{3,20})",
        r"(?:N[ºo]?\s*(?:DO\s*)?)REGISTRO\s*[:\-]?\s*([0-9A-Z\/\-]{3,20})",
        r"REGISTRO[^\d]{0,6}([0-9]{5,9})",
        r"SIGMA[^\d]{0,6}([0-9]{5,9})",
        r"CRAF[^\d]{0,6}([0-9]{5,9})",
    ]
    for p in patterns:
        m = re.search(p, texto, re.IGNORECASE)
        if not m:
            continue
        cand = _clean(m.group(1))
        # rejeita se for substring do serial (ex: serial ADK828440 -> 828440)
        if _is_in_serial(cand, serial_val):
            # ignora este candidato e continua procurando outras ocorrências
            continue
        if cand:
            numero_sigma = cand
            found_by = p
            break

    # 2) Se não achou com padrões, procura por sequências numéricas NÃO presentes no serial
    if not numero_sigma:
        # todos os números de 5-9 dígitos no texto
        all_nums = re.findall(r"\b([0-9]{5,9})\b", texto)
        # filtra os que aparecem dentro do serial
        candidates = [n for n in all_nums if not _is_in_serial(n, serial_val)]
        # preferir o número que esteja depois das palavras-chave "registro" ou "sigma"
        for keyword in ("REGISTRO", "SIGMA", "CRAF", "Nº", "Nº CRAF", "Nº SIGMA"):
            # procura por "keyword ... <num>"
            pat = rf"{keyword}[^\d]{{0,10}}([0-9]{{5,9}})"
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                cand = m.group(1)
                if not _is_in_serial(cand, serial_val):
                    numero_sigma = cand
                    found_by = f"keyword_{keyword}"
                    break
        # se ainda vazio, pega o primeiro candidate filtrado (se houver)
        if not numero_sigma and candidates:
            numero_sigma = candidates[0]
            found_by = "fallback_digits_filtered"

    # 3) Última tentativa: se LLM retornou campo "numero_documento" e ele não é substring do serial
    if not numero_sigma:
        possible = resultado_ia_field = None
        # resultado_ia pode não estar disponível dentro do escopo aqui se parse_craf for chamado por si só,
        # então verificamos apenas no texto: procura por "NUMERO_DOCUMENTO: 2207509" (caso IA tenha incluido isso)
        m = re.search(r"\bNUMERO_DOCUMENTO\b\s*[:\-]?\s*([0-9A-Z\/\-]{3,20})", txt_upper)
        if m:
            cand = _clean(m.group(1))
            if not _is_in_serial(cand, serial_val):
                numero_sigma = cand
                found_by = "numero_documento_field"

    # limpeza final e garantia de formato
    if numero_sigma:
        numero_sigma = numero_sigma.strip().upper()
        # se por algum acaso o numero_sigma ainda for substring do serial, preferimos "" (evita sobrescrita)
        if _is_in_serial(numero_sigma, serial_val):
            numero_sigma = ""
            found_by = None

    dados["numero_sigma"] = numero_sigma or ""
    if numero_sigma:
        dados["_debug_numero_sigma_found_by"] = found_by or "unknown"


    # EMISSOR
    dados["emissor_craf"] = ""
    for key, val in EMISSOR_MAP.items():
        if key in txt_upper:
            dados["emissor_craf"] = val
            break
    # Se o emissor foi normalizado como SIGMA/SINARM em EMISSOR_MAP, mantém

    # CATEGORIA DO ADQUIRENTE
    dados["categoria_adquirente"] = ""
    for key, val in CATEGORIA_MAP.items():
        if key in txt_upper:
            dados["categoria_adquirente"] = val
            break

    # VALIDADE
    m = re.search(r"\bVALIDADE\b\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
    if m:
        dados["data_validade_craf"] = m.group(1)
    else:
        datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
        dados["data_validade_craf"] = datas[-1] if datas else ""

    # DATA EMISSAO (opcional)
    m = re.search(r"EMISS[ÃA]O\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
    if m:
        dados["data_emissao_craf"] = m.group(1)

    # keep a small trace to help debugging if needed (não é log externo)
    if numero_sigma:
        dados["_debug_numero_sigma_found_by"] = found_by if 'found_by' in locals() else "unknown"

    return dados


def parse_cr(texto: str) -> dict:
    return {
        "numero_cr": _extract(r"\bCR\s*[:\-]?\s*([0-9]+)", texto),
        "nome": _extract(r"(?:NOME|TITULAR)[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "validade": _extract(r"VALIDADE[:\s]+(\d{2}/\d{2}/\d{4})", texto),
    }


def parse_cnh(texto: str) -> dict:
    return {
        "nome": _extract(r"\bNOME\b[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "registro": _extract(r"\bREGISTRO\b[:\s]*([0-9]+)", texto),
        "validade": _extract(r"\bVALIDADE\b[:\s]+(\d{2}/\d{2}/\d{4})", texto),
        "categoria": _extract(r"\bCATEGORIA\b[:\s]*([A-Z]+)", texto),
    }


def parse_rg(texto: str) -> dict:
    return {
        "nome": _extract(r"\bNOME\b[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "rg_numero": _extract(r"(?:\bRG\b|\bIDENTIDADE\b)[:\s]*([0-9\.A-Z\-]+)", texto),
        "orgao_emissor": _extract(r"(?:ÓRGÃO\s+EMISSOR|SSP)[:\s]+([A-Z]+)", texto),
    }

# =======================================
# PARSER INTELIGENTE (LLM + fallback)
# =======================================
from app.services.ocr_inteligente import interpretar_documento

def parse_documento_ocr(entrada) -> dict:
    """
    Novo parser inteligente híbrido:
    - Se receber texto OCR → envia à IA Groq
    - Se receber caminho de arquivo → faz OCR local e envia à IA
    - Retorna JSON padronizado (categoria, emissor, datas, etc.)
    """
    texto_extraido = ""

    # Caso 1: já é texto direto
    if isinstance(entrada, str) and not os.path.exists(entrada):
        texto_extraido = entrada
    # Caso 2: é caminho de arquivo
    else:
        caminho_arquivo = entrada
        if not os.path.exists(caminho_arquivo):
            return {}
        try:
            if caminho_arquivo.lower().endswith(".pdf"):
                paginas = convert_from_path(caminho_arquivo, dpi=200)
                for pagina in paginas:
                    texto_extraido += pytesseract.image_to_string(pagina, lang="por")
            else:
                img = Image.open(caminho_arquivo)
                texto_extraido = pytesseract.image_to_string(img, lang="por")
        except Exception as e:
            print("[OCR] Falha ao extrair texto local:", e)

    texto = _norm(texto_extraido)

    if not texto or len(texto) < 30:
        return {
            "categoria": "OUTRO",
            "emissor": "",
            "numero_documento": "",
            "data_emissao": "",
            "data_validade": "",
            "validade_indeterminada": False,
            "observacoes": "Texto insuficiente para análise."
        }

    # Envia para IA Groq (LLM)
    try:
        dados = interpretar_documento(texto)
        if isinstance(dados, dict):
            return dados
        else:
            return {"observacoes": "Interpretação inválida pelo LLM."}
    except Exception as e:
        print("[OCR] Erro ao enviar para Groq:", e)
        return {
            "categoria": "OUTRO",
            "emissor": "",
            "numero_documento": "",
            "data_emissao": "",
            "data_validade": "",
            "validade_indeterminada": False,
            "observacoes": f"Erro ao processar via LLM: {e}"
        }
