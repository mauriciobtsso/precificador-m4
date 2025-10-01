# app/utils/parcelamento_helpers.py
from app.utils.number_helpers import to_float


def montar_parcelas(valor_base, taxas, modo="coeficiente_total"):
    """
    Gera uma lista de opções de parcelamento.

    - valor_base: valor original
    - taxas: lista de objetos Taxa (com .numero_parcelas e .juros)
    - modo: "coeficiente_total" (desconto único) ou "juros_mensal"
    """
    resultado = []
    base = float(valor_base or 0)

    for taxa in taxas:
        n = int(taxa.numero_parcelas or 1)
        j = max(to_float(taxa.juros), 0.0) / 100.0
        if n <= 0:
            continue

        if n == 1 and modo == "coeficiente_total":
            # desconto único (exemplo: débito à vista)
            coef = max(1.0 - j, 1e-9)
            total = base / coef
            parcela = total
        else:
            if modo == "juros_mensal":
                if j > 0:
                    parcela = base * (j / (1 - (1 + j) ** (-n)))
                else:
                    parcela = base / n
                total = parcela * n
            else:
                coef = max(1.0 - j, 1e-9)
                total = base / coef
                parcela = total / n

        resultado.append({
            "parcelas": n,
            "parcela": parcela,
            "total": total,
            "diferenca": total - base,
            "rotulo": "Débito" if n == 1 else f"{n}x",
        })

    return resultado
