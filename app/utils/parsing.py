"""Conversões de valores recebidos por formulários web."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from app.utils.datetime import TZ_FORTALEZA


def parse_decimal(value):
    """Converte valores brasileiros (ex.: ``2.050,00``) para Decimal."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    try:
        cleaned = re.sub(r"[^\d,.-]", "", str(value))
        if not cleaned:
            return None
        if "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_local_datetime(value):
    """Converte ``datetime-local`` para datetime aware no fuso da aplicação.

    O input HTML não envia fuso horário. Portanto, a data/hora digitada pelo
    usuário é interpretada como horário local de Fortaleza e armazenada com
    informação explícita de fuso, evitando comparações inválidas com now_local.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return TZ_FORTALEZA.localize(value)
        return value.astimezone(TZ_FORTALEZA)

    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        return TZ_FORTALEZA.localize(parsed)
    return parsed.astimezone(TZ_FORTALEZA)


def as_local_aware(value):
    """Normaliza datetimes do banco, inclusive valores sem tzinfo."""
    if value is None:
        return None
    if value.tzinfo is None:
        return TZ_FORTALEZA.localize(value)
    return value.astimezone(TZ_FORTALEZA)


def parse_form_datetime(value):
    """Alias semântico para uso nas rotas de formulário."""
    return parse_local_datetime(value)
