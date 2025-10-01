# app/utils/converters.py
# ------------------------------------------------------------
# Funções de conversão genéricas
# ------------------------------------------------------------

def to_float(value, default=0.0):
    """
    Converte um valor para float.
    Aceita números com vírgula ou ponto como separador decimal.
    Retorna 'default' se não conseguir converter.
    """
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return default
