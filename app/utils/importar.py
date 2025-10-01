# app/utils/importar.py

def _headers_lower(ws):
    """
    Normaliza os cabeçalhos da planilha para minúsculo.
    """
    headers = []
    for cell in ws[1]:
        if cell.value:
            headers.append(str(cell.value).strip().lower())
        else:
            headers.append("")
    return headers


def _row_as_dict(headers, row):
    """
    Converte uma linha da planilha em dict usando os headers.
    """
    data = {}
    for header, value in zip(headers, row):
        data[header] = value
    return data


def _get(data: dict, key: str, default=None):
    """
    Acessa uma chave em dict com segurança, retornando default se não existir.
    """
    try:
        return data.get(key, default)
    except Exception:
        return default
