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
# MAPAS DE NORMALIZAÇÃO
# ======================
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


# ======================
# PARSER CRAF
# ======================
def parse_craf(texto: str) -> dict:
    dados = {}
    STOP = r"(?:TIPO|MARCA|MODELO|CALIBRE|FUNCIONAMENTO|EMISSOR|N[ºo]?\s*(?:DE\s*)?S[ÉE]RIE|N[ºo]?\s+SIGMA|VALIDADE|CATEGORIA|DATA|EXPEDIÇÃO|\n|$)"
    txt_upper = _norm(texto).upper()

    # Tipo
    tipo_detectado = _extract(rf"\bTIPO\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", txt_upper).upper()
    if not tipo_detectado:
        m2 = re.search(r"\b(PISTOLA|REVOLVER|REVÓLVER|CARABINA|FUZIL|ESPINGARDA|GARRUNCHA)\b", txt_upper, re.I)
        tipo_detectado = m2.group(1).upper() if m2 else ""
    dados["tipo"] = TIPO_MAP.get(tipo_detectado, "")

    # Funcionamento
    funcionamento_detectado = _extract(rf"\bFUNCIONAMENTO\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", txt_upper).upper()
    dados["funcionamento"] = ""
    for key, val in FUNCIONAMENTO_MAP.items():
        if key in funcionamento_detectado:
            dados["funcionamento"] = val
            break
        if key in txt_upper:
            dados["funcionamento"] = val
            break

    # Marca (livre)
    m = re.search(rf"\bMARCA\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    dados["marca"] = _norm(m.group(1)).title() if m else ""

    # Modelo (livre)
    m = re.search(rf"\bMODELO\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    dados["modelo"] = _norm(m.group(1)).title() if m else ""

    # Calibre
    m = re.search(rf"\bCALIBRE\b\s*[:\-]?\s*([^\n]+?)\s*(?={STOP})", texto, re.I)
    if m:
        cal = _norm(m.group(1))
        cal = cal.replace("X", "x").replace("MM", "mm").replace("Mm", "mm")
        dados["calibre"] = cal
    else:
        dados["calibre"] = ""

    # Nº Série
    m = re.search(rf"(?:N[ºo]?\s*(?:DE\s*)?)?S[ÉE]RIE\s*[:\-]?\s*([A-Z0-9\-]{{3,20}})\s*(?={STOP})", texto, re.I)
    if not m:
        m = re.search(r"\b([A-Z]{1,4}[0-9]{3,10})\b", texto)
    dados["numero_serie"] = _norm(m.group(1)).upper() if m else ""

    # Emissor
    dados["emissor_craf"] = ""
    for key, val in EMISSOR_MAP.items():
        if key in txt_upper:
            dados["emissor_craf"] = val
            break

    # Categoria do Adquirente
    dados["categoria_adquirente"] = ""
    for key, val in CATEGORIA_MAP.items():
        if key in txt_upper:
            dados["categoria_adquirente"] = val
            break

    # Validade
    m = re.search(r"\bVALIDADE\b\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
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
        "nome": _extract(r"\bNOME\b[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "registro": _extract(r"\bREGISTRO\b[:\s]*([0-9]+)", texto),
        "validade": _extract(r"\bVALIDADE\b[:\s]+(\d{2}/\d{2}/\d{4})", texto),
        "categoria": _extract(r"\bCATEGORIA\b[:\s]*([A-Z]+)", texto),
    }


# ======================
# PARSER RG
# ======================
def parse_rg(texto: str) -> dict:
    return {
        "nome": _extract(r"\bNOME\b[:\s]+([A-Z\s]+)", texto, transform=str.title),
        "cpf": _extract(r"(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", texto),
        "rg_numero": _extract(r"(?:\bRG\b|\bIDENTIDADE\b)[:\s]*([0-9\.A-Z\-]+)", texto),
        "orgao_emissor": _extract(r"(?:ÓRGÃO\s+EMISSOR|SSP)[:\s]+([A-Z]+)", texto),
    }
