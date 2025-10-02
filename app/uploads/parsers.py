import re

# ======================
# HELPERS
# ======================
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


# ======================
# PARSER CRAF
# ======================
def parse_craf(texto: str) -> dict:
    dados = {}

    STOP = r"(?:TIPO|MARCA|MODELO|CALIBRE|N[ºo]\s*S[ÉE]RIE|N[ºo]\s+SIGMA|VALIDADE|DATA|\n|$)"

    # Tipo
    m = re.search(rf"\bTIPO\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    if m:
        dados["tipo"] = _norm(m.group(1)).upper()
    else:
        m2 = re.search(r"\b(PISTOLA|REVOLVER|CARABINA|ESPINGARDA)\b", texto, re.I)
        dados["tipo"] = m2.group(1).upper() if m2 else ""

    # Marca
    m = re.search(rf"\bMARCA\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    dados["marca"] = _norm(m.group(1)).title() if m else ""

    # Modelo (opcional)
    m = re.search(rf"\bMODELO\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    dados["modelo"] = _norm(m.group(1)).title() if m else ""

    # Calibre
    m = re.search(rf"\bCALIBRE\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    if m:
        dados["calibre"] = (_norm(m.group(1))
                            .replace("X", "x")
                            .replace("Mm", "mm")
                            .replace("MM", "mm"))
    else:
        dados["calibre"] = ""

    # Nº Série
    m = re.search(rf"(?:N[ºo]\s*)?S[ÉE]RIE\s*[:\-]?\s*([A-Z0-9\-]{3,20})\s*(?={STOP})", texto, re.I)
    if not m:
        m = re.search(r"\b([A-Z]{1,4}[0-9]{3,10})\b", texto)
    dados["numero_serie"] = _norm(m.group(1)).upper() if m else ""

    # Validade
    m = re.search(r"\bVALIDADE\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
    if m:
        dados["data_validade_craf"] = m.group(1)
    else:
        datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
        dados["data_validade_craf"] = datas[-1] if datas else ""

    return dados


# ======================
# PARSER CR
# ======================
def parse_cr(texto: str) -> dict:
    return {
        "numero_cr": _extract(r"\bCR\s*[:\-]?\s*([0-9]+)", texto),
        "nome": _extract(r"(?:NOME|TITULAR)[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "validade": _extract(r"VALIDADE[:\s]+(\d{2}/\d{2}/\d{4})", texto),
    }


# ======================
# PARSER CNH
# ======================
def parse_cnh(texto: str) -> dict:
    return {
        "nome": _extract(r"NOME[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "registro": _extract(r"REGISTRO[:\s]*([0-9]+)", texto),
        "validade": _extract(r"VALIDADE[:\s]+(\d{2}/\d{2}/\d{4})", texto),
        "categoria": _extract(r"CATEGORIA[:\s]*([A-Z]+)", texto),
    }


# ======================
# PARSER RG
# ======================
def parse_rg(texto: str) -> dict:
    return {
        "nome": _extract(r"NOME[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "rg_numero": _extract(r"(?:RG|IDENTIDADE)[:\s]*([0-9\.A-Z\-]+)", texto),
        "orgao_emissor": _extract(r"(?:ÓRGÃO\s+EMISSOR|SSP)[:\s]+([A-Z]+)", texto),
    }
