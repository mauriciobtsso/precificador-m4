from datetime import datetime


def parse_date(value):
    """
    Converte 'YYYY-MM-DD' ou 'DD/MM/YYYY' para datetime.date.
    Retorna None se vazio ou inválido.
    """
    if not value or not str(value).strip():
        return None

    formatos = ("%Y-%m-%d", "%d/%m/%Y")

    for fmt in formatos:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue

    return None
