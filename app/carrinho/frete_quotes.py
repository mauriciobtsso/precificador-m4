"""Assinatura de opções de frete para evitar confiar em preço enviado pelo browser."""
import hashlib
import hmac
import json
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
QUOTE_TTL_SECONDS = 15 * 60


def money(value):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Valor de frete inválido.") from exc
    if not amount.is_finite():
        raise ValueError("Valor de frete inválido.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def cart_fingerprint(carrinho):
    rows = []
    for item in carrinho.items:
        rows.append([
            int(item.produto_id),
            int(item.quantidade),
            format(money(item.preco_unitario_no_momento), ".2f"),
        ])
    rows.sort()
    data = json.dumps(rows, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _material(cep, option_id, name, price, prazo, fingerprint, expires_at):
    return json.dumps([
        str(cep), str(option_id), str(name), format(money(price), ".2f"),
        str(prazo), str(fingerprint), int(expires_at),
    ], separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def issue_quote(cep, option_id, name, price, prazo, fingerprint, secret, now=None):
    expires_at = int(now if now is not None else time.time()) + QUOTE_TTL_SECONDS
    key = str(secret or "").encode("utf-8")
    token = hmac.new(key, _material(cep, option_id, name, price, prazo, fingerprint, expires_at), hashlib.sha256).hexdigest()
    return token, expires_at


def validate_quote(cep, option_id, name, price, prazo, fingerprint, token, expires_at, secret, now=None):
    try:
        expires_at = int(expires_at)
        current_time = int(now if now is not None else time.time())
        if expires_at <= current_time or expires_at > current_time + QUOTE_TTL_SECONDS + 5:
            return False
        key = str(secret or "").encode("utf-8")
        expected = hmac.new(key, _material(cep, option_id, name, price, prazo, fingerprint, expires_at), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, str(token or ""))
    except (TypeError, ValueError, InvalidOperation):
        return False
