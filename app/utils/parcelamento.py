# app/utils/parcelamento.py
from typing import Iterable, List, Dict

from typing import List, Dict, Iterable

def gerar_linhas_parcelas(valor_base: float, taxas: Iterable) -> List[Dict[str, float]]:
    """
    Gera linhas de parcelamento com base em uma lista de taxas.
    Cada taxa deve ter:
      - numero_parcelas (int)
      - juros (float, percentual)
    """
    base = float(valor_base or 0.0)
    linhas: List[Dict[str, float]] = []

    # Ordena pelas parcelas
    taxas_ordenadas = sorted(
        list(taxas),
        key=lambda t: int(getattr(t, "numero_parcelas", 1))
    )

    for t in taxas_ordenadas:
        n = max(0, int(getattr(t, "numero_parcelas", 0)))
        j_percent = float(getattr(t, "juros", 0.0))

        # converte juros percentual em coeficiente
        j = j_percent / 100.0
        coef = max(1.0 - j, 1e-9)

        total = base / coef
        parcela = total / (n if n > 0 else 1)

        # Rotulo especial para 0x
        rotulo = "Débito" if n == 0 else f"{n}x"

        linhas.append({
            "rotulo": rotulo,
            "parcela": parcela,
            "total": total
        })

    return linhas
