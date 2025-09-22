# app/utils/whatsapp.py

def gerar_mensagem_whatsapp(produto, valor_base, linhas):
    msg = []

    # Cabeçalho
    if produto:
        msg.append(f"🔫 {produto.nome.upper()}")
        msg.append(f"🔖 SKU: {produto.sku}")
        msg.append(f"💰 À vista: R$ {valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        msg.append("")
    else:
        msg.append("💰 Simulação de Parcelamento")
        msg.append(f"Valor base: R$ {valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        msg.append("")

    msg.append("💳 Opções de Parcelamento:")

    # Corpo
    for linha in linhas:
        rotulo = linha.get("rotulo", "N/A")
        parcela = linha.get("parcela", 0)
        total = linha.get("total", valor_base)

        # formata os números separadamente (sem alterar os rótulos)
        total_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        parcela_fmt = f"R$ {parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        if rotulo == "PIX":
            msg.append(f"PIX {total_fmt}")
        elif rotulo == "Débito":
            msg.append(f"Débito {total_fmt}")
        elif rotulo == "1x":
            msg.append(f"1x {total_fmt}")
        else:
            msg.append(f"{rotulo} {parcela_fmt} = {total_fmt}")

    # Rodapé
    msg.append("")
    msg.append("⚠️ Os valores poderão sofrer alterações sem aviso prévio.")

    return "\n".join(msg)
