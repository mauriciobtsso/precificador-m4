# app/utils/numeros.py

def to_float(value):
    """
    Converte string/valor em float.
    Aceita vírgula ou ponto como separador decimal.
    Retorna 0.0 em caso de erro.
    """
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def to_number(value):
    """
    Converte para float ou retorna None se vazio/inválido.
    """
    try:
        return float(value) if value not in [None, ""] else None
    except Exception:
        return None
