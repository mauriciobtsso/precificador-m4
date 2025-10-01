from app.utils.format_helpers import br_money
from app.config import get_config


def compor_whatsapp(produto=None, valor_base=0.0, linhas=None):
    """
    Monta a mensagem de parcelamento para envio via WhatsApp.
    """
    base = float(valor_base or 0)
    linhas = linhas or []

    prefixo = get_config("whatsapp_prefixo", "")

    cab = []
    if prefixo:
        cab.append(prefixo)

    if produto:
        cab.append(f"🔫 {produto.nome}")
        cab.append(f"🔖 SKU: {produto.sku}")
        cab.append(f"💰 À vista: {br_money(base)}")
    else:
        cab.append("💳 Simulação de Parcelamento")
        cab.append(f"💰 À vista: {br_money(base)}")

    corpo = []
    corpo.append(f"PIX {br_money(base)}")  # PIX sempre fixo

    for r in linhas:
        rotulo = r["rotulo"]
        if rotulo.lower() == "pix":
            continue
        if rotulo.lower() == "débito":
            corpo.append(f"Débito {br_money(r['total'])}")
        else:
            corpo.append(f"{rotulo} {br_money(r['parcela'])} = {br_money(r['total'])}")

    txt = "\n".join(cab) + "\n\n" + "💳 Opções de Parcelamento:\n" + "\n".join(corpo)
    txt += "\n\n⚠️ Os valores poderão sofrer alterações sem aviso prévio."
    return txt


def gerar_texto_whatsapp(produto, valor_base, linhas):
    """Atalho para compor_whatsapp (compatibilidade)."""
    return compor_whatsapp(produto, valor_base, linhas)
