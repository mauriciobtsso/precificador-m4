"""Helpers de SEO técnico para a vitrine pública da M4 Tática."""

from datetime import date, datetime
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

from flask import request


CANONICAL_STORE_ORIGIN = "https://loja.m4tatica.com.br"
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
register_namespace("", SITEMAP_NAMESPACE)


def canonical_store_url(path=None):
    """Retorna uma URL do host público e remove o prefixo interno ``/loja``."""
    raw_path = request.path if path is None else str(path)
    parsed_path = urlsplit(raw_path)
    if parsed_path.netloc and parsed_path.hostname != "loja.m4tatica.com.br":
        return f"{CANONICAL_STORE_ORIGIN}/"
    normalized_path = parsed_path.path or "/"

    if normalized_path == "/loja":
        normalized_path = "/"
    elif normalized_path.startswith("/loja/"):
        normalized_path = normalized_path[len("/loja"):]

    if not normalized_path.startswith("/") or normalized_path.startswith("//"):
        normalized_path = "/"

    return f"{CANONICAL_STORE_ORIGIN}{normalized_path}"


def build_sitemap_xml(entries):
    """Gera XML de sitemap com URLs canônicas e lastmod somente quando informado.

    Cada entrada deve ser uma tupla ``(caminho, data_ultima_alteracao)``.
    A data pode ser ``date``, ``datetime``, texto ISO ou ``None``.
    """
    root = Element(f"{{{SITEMAP_NAMESPACE}}}urlset")

    for path, lastmod in entries:
        url_element = SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
        SubElement(url_element, f"{{{SITEMAP_NAMESPACE}}}loc").text = canonical_store_url(path)

        if lastmod:
            if isinstance(lastmod, datetime):
                lastmod_value = lastmod.date().isoformat()
            elif isinstance(lastmod, date):
                lastmod_value = lastmod.isoformat()
            else:
                lastmod_value = str(lastmod)
            SubElement(url_element, f"{{{SITEMAP_NAMESPACE}}}lastmod").text = lastmod_value

    return tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
