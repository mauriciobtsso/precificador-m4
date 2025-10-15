def calcular_precificacao(custo=0, frete=0, margem=0, **kw):
    custo_total = float(custo) + float(frete)
    venda = custo_total * (1 + float(margem)/100)
    return dict(custo_total=custo_total, preco_venda=venda, lucro=venda-custo_total)
