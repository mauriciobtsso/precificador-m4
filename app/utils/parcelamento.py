# app/utils/parcelamento.py
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

    # Ordena pelas parcelas (0x, 1x, 2x, ...)
    taxas_ordenadas = sorted(
        list(taxas),
        key=lambda t: int(getattr(t, "numero_parcelas", 1))
    )

    for t in taxas_ordenadas:
        n = int(getattr(t, "numero_parcelas", 0))
        j_percent = float(getattr(t, "juros", 0.0))

        # Converte juros percentual em coeficiente
        j = j_percent / 100.0
        coef = max(1.0 - j, 1e-9)

        total = base / coef
        parcela = total / (n if n > 0 else 1)

        # Rótulo especial para 0x
        rotulo = "Débito" if n == 0 else f"{n}x"

        # Débito e 1x não mostram o "= total" no texto final (apenas valor da parcela)
        linhas.append({
            "rotulo": rotulo,
            "parcela": parcela,
            "total": total,
            "mostrar_total": False if n in (0, 1) else True
        })

    return linhas
