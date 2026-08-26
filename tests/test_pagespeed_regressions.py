from pathlib import Path

import pytest
from flask import Flask, session

from app.loja.routes import _index_cache_key, normalizar_foto_loja


ROOT = Path(__file__).resolve().parents[1]
LOJA_TEMPLATES = ROOT / "app" / "loja" / "templates" / "loja"


def test_store_templates_do_not_emit_broken_image_proxy_urls():
    templates = "\n".join(path.read_text(encoding="utf-8") for path in LOJA_TEMPLATES.glob("*.html"))
    assert "wsrv.nl" not in templates
    assert "logo-social.png" not in templates


def test_home_seo_uses_expected_block_and_current_store_origin():
    home = (LOJA_TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "{% block seo_meta %}" in home
    assert "{% block meta_description %}" not in home
    assert "app.m4tatica.com.br/loja" not in home
    assert "url_for('loja.index', _external=True)" in home


def test_store_icon_subset_contains_all_icons_used_by_store_templates():
    import re

    sources = "\n".join(path.read_text(encoding="utf-8") for path in LOJA_TEMPLATES.glob("*.html"))
    sources += "\n" + (ROOT / "app/static/js/cart-handler.js").read_text(encoding="utf-8")
    used = set(re.findall(r"bi-[a-z0-9-]+", sources))
    subset = (ROOT / "app/static/vendor/bootstrap-icons/bootstrap-icons-loja.css").read_text(encoding="utf-8")
    missing = [name for name in sorted(used) if f".{name}::before" not in subset]
    assert not missing, f"Ícones ausentes na folha reduzida: {missing}"


def test_index_cache_key_varies_by_store_customer_session():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.test_request_context("/?q=pistola"):
        anonymous_key = _index_cache_key()
        session["loja_cliente_id"] = 42
        customer_key = _index_cache_key()
    assert anonymous_key != customer_key
    assert "cliente:anon" in anonymous_key
    assert "cliente:42" in customer_key
    assert "q=pistola" in customer_key


def test_normalize_store_photo_falls_back_to_local_placeholder():
    app = Flask(__name__)
    with app.test_request_context("/"):
        assert normalizar_foto_loja(None) == "/static/img/sem-foto.jpg"
        assert normalizar_foto_loja("") == "/static/img/sem-foto.jpg"


def test_security_configuration_is_present_in_app_factory():
    source = (ROOT / "app/__init__.py").read_text(encoding="utf-8")
    assert "content_security_policy=loja_csp" in source
    assert "strict_transport_security=True" in source
    assert "Cross-Origin-Opener-Policy" in source


def test_store_home_renders_optimized_html_and_security_headers(client):
    response = client.get("/loja/", base_url="https://loja.m4tatica.com.br")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'meta name="description"' in html
    assert 'bootstrap-icons-loja.css' in html
    assert "wsrv.nl" not in html
    assert "logo-social.png" not in html
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"
