"""Cálculos e payload de checkout da loja pública.

Os valores aqui são snapshots de venda; não alteram a precificação nem a margem
usadas pelos fluxos internos de produtos.
"""
from decimal import Decimal, ROUND_HALF_UP
from app.models import Configuracao

CENT = Decimal("0.01")
PIX_DISCOUNT_PERCENT = Decimal("0.00")
PIX_EXPIRATION_SECONDS = 60 * 60


def obter_desconto_pix_percentual():
    """Retorna o percentual configurado para o PIX, com padrão seguro de zero."""
    ativo = Configuracao.query.filter_by(chave="loja_pix_desconto_ativo").first()
    percentual = Configuracao.query.filter_by(chave="loja_pix_desconto_percentual").first()
    if not ativo or str(ativo.valor or "") != "1":
        return PIX_DISCOUNT_PERCENT
    try:
        valor = Decimal(str(percentual.valor or "0")) if percentual else PIX_DISCOUNT_PERCENT
    except Exception:
        return PIX_DISCOUNT_PERCENT
    if not valor.is_finite() or valor < 0 or valor > 100:
        return PIX_DISCOUNT_PERCENT
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money(value):
    try:
        amount = Decimal(str(value or 0))
    except Exception as exc:
        raise ValueError("Valor monetário inválido.") from exc
    if not amount.is_finite():
        raise ValueError("Valor monetário inválido.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value):
    return int(money(value) * 100)


def calcular_snapshot_pix(itens, frete, desconto_percentual=PIX_DISCOUNT_PERCENT):
    """Retorna produtos/frete/base/desconto/final com desconto configurável."""
    try:
        desconto_percentual = Decimal(str(desconto_percentual or "0"))
    except Exception as exc:
        raise ValueError("Percentual de desconto PIX inválido.") from exc
    if not desconto_percentual.is_finite() or not 0 <= desconto_percentual <= 100:
        raise ValueError("Percentual de desconto PIX inválido.")
    linhas = []
    total_produtos = Decimal("0.00")
    total_produtos_pix = Decimal("0.00")
    for item in itens:
        quantidade = int(item.quantidade or 0)
        if quantidade <= 0:
            raise ValueError("A quantidade de um item do carrinho é inválida.")
        unitario = money(item.preco_unitario_no_momento)
        unitario_pix = money(unitario * (Decimal("1") - desconto_percentual / Decimal("100")))
        subtotal = money(unitario * quantidade)
        subtotal_pix = money(unitario_pix * quantidade)
        linhas.append({"item": item, "unitario": unitario, "unitario_pix": unitario_pix,
                       "subtotal": subtotal, "subtotal_pix": subtotal_pix})
        total_produtos += subtotal
        total_produtos_pix += subtotal_pix

    total_produtos = money(total_produtos)
    total_produtos_pix = money(total_produtos_pix)
    total_frete = money(frete)
    if total_frete < 0:
        raise ValueError("Valor de frete inválido.")
    total_base = money(total_produtos + total_frete)
    desconto = money(total_produtos - total_produtos_pix)
    total_cobrado = money(total_produtos_pix + total_frete)

    return {
        "linhas": linhas,
        "total_produtos": total_produtos,
        "total_produtos_pix": total_produtos_pix,
        "total_frete": total_frete,
        "total_base": total_base,
        "desconto_aplicado": desconto,
        "desconto_percentual": desconto_percentual,
        "total_cobrado": total_cobrado,
        "taxa_aplicada": Decimal("0.0000"),
        "parcelas": 1,
        "valor_parcela": total_cobrado,
    }


def _digits(value):
    return "".join(char for char in str(value or "") if char.isdigit())


def _address(data):
    line_1 = ", ".join(part for part in [data["numero"], data["logradouro"], data["bairro"]] if part)
    state = str(data["estado"]).strip().upper()
    if not state.startswith("BR-"):
        state = f"BR-{state}"
    address = {
        "country": "BR",
        "state": state,
        "city": data["cidade"],
        "zip_code": data["cep"],
        "line_1": line_1[:256],
    }
    complement = str(data.get("complemento") or "").strip()
    if complement:
        address["line_2"] = complement[:128]
    return address


def construir_payload_pix(pedido, snapshot, dados_cliente, nome_frete):
    """Monta o POST /orders sem incluir dados de cartão ou segredos."""
    telefone = _digits(dados_cliente["telefone"])
    documento = _digits(dados_cliente["documento"])
    address = _address(dados_cliente)
    items = []
    for linha in snapshot["linhas"]:
        produto = linha["item"].produto
        if linha["unitario_pix"] <= 0:
            continue
        items.append({
            "amount": to_cents(linha["unitario_pix"]),
            "description": str((getattr(produto, "nome_comercial", None) or produto.nome) if produto else "Produto")[:255],
            "quantity": int(linha["item"].quantidade),
            "code": str((getattr(produto, "codigo", None) or getattr(produto, "id", "produto")))[:52],
        })

    if not items:
        raise ValueError("O pedido precisa conter ao menos um produto com valor maior que zero.")
    if snapshot["total_cobrado"] <= 0:
        raise ValueError("O total do pedido precisa ser maior que zero.")

    area_code, phone_number = telefone[:2], telefone[2:]
    nome = str(dados_cliente["nome"]).strip()[:64]
    email = str(dados_cliente["email"]).strip().lower()[:64]
    customer = {
        "name": nome,
        "email": email,
        "type": "individual" if len(documento) == 11 else "company",
        "document": documento,
        "document_type": "CPF" if len(documento) == 11 else "CNPJ",
        "address": address,
        "phones": {"mobile_phone": {
            "country_code": "55", "area_code": area_code, "number": phone_number,
        }},
    }

    payload = {
        "code": str(pedido.public_id),
        "items": items,
        "customer": customer,
        "payments": [{
            "payment_method": "pix",
            "pix": {"expires_in": PIX_EXPIRATION_SECONDS},
        }],
    }
    if snapshot["total_frete"] > 0 or nome_frete:
        payload["shipping"] = {
            "amount": to_cents(snapshot["total_frete"]),
            "description": str(nome_frete or "Frete")[:255],
            "recipient_name": nome,
            "recipient_phone": telefone,
            "address": address,
        }
    return payload


def extrair_dados_pix(pedido_gateway):
    """Localiza QR Code/copia e cola na resposta de criação ou consulta."""
    for charge in pedido_gateway.get("charges") or []:
        transaction = charge.get("last_transaction") or {}
        tipo = str(transaction.get("transaction_type") or charge.get("payment_method") or "").lower()
        if "pix" not in tipo:
            continue
        return {
            "codigo": transaction.get("qr_code"),
            "url": transaction.get("qr_code_url"),
            "expira_em": transaction.get("expires_at"),
        }
    return {"codigo": None, "url": None, "expira_em": None}


def status_local_pagarme(status):
    status = str(status or "").strip().lower()
    if status == "paid":
        return "pago"
    if status in {"refunded", "partially_refunded"}:
        return "estornado"
    if status in {"canceled", "cancelled", "failed", "payment_failed"}:
        return "cancelado"
    return "pendente"
