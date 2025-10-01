# app/utils/excel_helpers.py

def _headers_lower(ws):
    """Retorna cabeçalhos da primeira linha em minúsculo."""
    return [str(c.value).strip().lower() if c.value is not None else "" for c in ws[1]]


def _row_as_dict(headers_lower, row_values):
    """Converte uma linha da planilha em dict usando os cabeçalhos."""
    return {h: v for h, v in zip(headers_lower, row_values) if h}


def _get(d, *names, default=None):
    """Busca valor em dict usando nomes alternativos de chave."""
    for name in names:
        key = str(name).strip().lower()
        if key in d and d[key] not in (None, ""):
            return d[key]
    return default


def _as_bool(val):
    """Converte string/num em booleano."""
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("1", "sim", "true", "verdadeiro", "yes", "y")
