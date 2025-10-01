# app/utils/number_helpers.py

def to_float(value, default=0.0):
    """Converte string ou número para float de forma segura."""
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def parse_brl(s) -> float:
    """Converte string monetária (R$) para float."""
    if s is None:
        return 0.0
    s = str(s).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace("r$", "").strip()
    s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_pct(s) -> float:
    """Converte string percentual (%) para float."""
    if s is None:
        return 0.0
    s = str(s).strip().replace("%", "").replace(",", ".")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0
