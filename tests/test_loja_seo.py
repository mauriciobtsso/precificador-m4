import json
import re
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from xml.etree.ElementTree import fromstring

from app import db
from app.loja.models_admin import PaginaInstitucional
from app.loja.routes import cache
from app.loja.seo import SITEMAP_NAMESPACE, build_sitemap_xml, canonical_store_url
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.models import Produto


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_store_url_always_uses_public_host_and_removes_internal_prefix():
    assert canonical_store_url("/loja/") == "https://loja.m4tatica.com.br/"
    assert canonical_store_url("/loja/produto/taurus-abc?utm_source=x") == (
        "https://loja.m4tatica.com.br/produto/taurus-abc"
    )
    assert canonical_store_url("/produto/taurus-abc") == (
        "https://loja.m4tatica.com.br/produto/taurus-abc"
    )
    assert canonical_store_url("//example.invalid/path") == "https://loja.m4tatica.com.br/"


def test_sitemap_xml_has_public_canonical_urls_and_optional_lastmod():
    xml = build_sitemap_xml([
        ("/loja/", None),
        ("/loja/produto/item-exemplo", date(2026, 10, 13)),
    ])
    root = fromstring(xml)
    urls = root.findall(f"{{{SITEMAP_NAMESPACE}}}url")

    assert len(urls) == 2
    assert urls[0].findtext(f"{{{SITEMAP_NAMESPACE}}}loc") == "https://loja.m4tatica.com.br/"
    assert urls[0].find(f"{{{SITEMAP_NAMESPACE}}}lastmod") is None
    assert urls[1].findtext(f"{{{SITEMAP_NAMESPACE}}}loc") == (
        "https://loja.m4tatica.com.br/produto/item-exemplo"
    )
    assert urls[1].findtext(f"{{{SITEMAP_NAMESPACE}}}lastmod") == "2026-10-13"


def test_robots_txt_declares_only_xml_sitemap():
    robots = (REPO_ROOT / "app" / "static" / "robots.txt").read_text(encoding="utf-8")
    sitemap_lines = [line for line in robots.splitlines() if line.lower().startswith("sitemap:")]

    assert sitemap_lines == ["Sitemap: https://loja.m4tatica.com.br/sitemap.xml"]


def test_store_home_exposes_primary_catalog_cta_and_public_canonical(client):
    response = client.get("/loja/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<h1 id="loja-home-titulo"' in html
    assert 'href="#catalogo"' in html
    assert 'id="catalogo"' in html
    assert '<link rel="canonical" href="https://loja.m4tatica.com.br/">' in html
    assert "precificador-m4.onrender.com" not in html


def test_unknown_store_url_returns_custom_noindex_404(client):
    response = client.get("/loja/rota-seo-inexistente-404")
    html = response.get_data(as_text=True)

    assert response.status_code == 404
    assert "Não encontramos esta página" in html
    assert 'name="robots" content="noindex, follow"' in html
    assert response.headers.get("X-Robots-Tag") == "noindex, follow"
    assert "https://loja.m4tatica.com.br/" in html


def test_unknown_json_route_keeps_json_404_response(client):
    response = client.get("/api/rota-inexistente", headers={"Accept": "application/json"})

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "not_found"
    assert response.headers.get("X-Robots-Tag") == "noindex, follow"


def test_public_sitemap_is_xml_and_uses_official_host(client):
    response = client.get("/sitemap.xml")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    assert "https://loja.m4tatica.com.br/" in body
    assert "https://loja.m4tatica.com.br/perguntas-frequentes" in body
    assert "precificador-m4.onrender.com" not in body


def test_sitemap_includes_public_products_and_pages_but_excludes_empty_or_hidden_content(app, client):
    token = uuid4().hex[:12]
    parent = CategoriaProduto(nome=f"SEO pai {token}", slug=f"seo-pai-{token}")
    child = CategoriaProduto(nome=f"SEO filha {token}", slug=f"seo-filha-{token}", pai=parent)
    empty = CategoriaProduto(nome=f"SEO vazia {token}", slug=f"seo-vazia-{token}")
    hidden_category = CategoriaProduto(nome=f"SEO oculta {token}", slug=f"seo-oculta-{token}")
    page = PaginaInstitucional(
        titulo=f"SEO página {token}",
        slug=f"seo-pagina-{token}",
        conteudo="Conteúdo público de teste.",
        visivel_rodape=True,
    )
    hidden_page = PaginaInstitucional(
        titulo=f"SEO privada {token}",
        slug=f"seo-privada-{token}",
        conteudo="Conteúdo não publicado de teste.",
        visivel_rodape=False,
    )
    with app.app_context():
        db.session.add_all([parent, child, empty, hidden_category, page, hidden_page])
        db.session.flush()
        product = Produto(
            codigo=f"SEO-{token}",
            nome=f"Produto SEO {token}",
            slug=f"produto-seo-{token}",
            visivel_loja=True,
            categoria_id=child.id,
            atualizado_em=datetime(2026, 10, 13, 12, 0, 0),
        )
        hidden_product = Produto(
            codigo=f"HID-{token}",
            nome=f"Produto oculto SEO {token}",
            slug=f"produto-oculto-seo-{token}",
            visivel_loja=False,
            categoria_id=hidden_category.id,
        )
        db.session.add_all([product, hidden_product])
        db.session.commit()
        cache.clear()

    try:
        response = client.get("/sitemap.xml")
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert f"https://loja.m4tatica.com.br/produto/produto-seo-{token}" in body
        assert f"https://loja.m4tatica.com.br/categoria/seo-pai-{token}" in body
        assert f"https://loja.m4tatica.com.br/categoria/seo-filha-{token}" in body
        assert f"https://loja.m4tatica.com.br/p/seo-pagina-{token}" in body
        assert f"produto-oculto-seo-{token}" not in body
        assert f"seo-oculta-{token}" not in body
        assert f"seo-vazia-{token}" not in body
        assert f"seo-privada-{token}" not in body
    finally:
        with app.app_context():
            db.session.delete(product)
            db.session.delete(hidden_product)
            db.session.delete(page)
            db.session.delete(hidden_page)
            db.session.delete(child)
            db.session.delete(parent)
            db.session.delete(empty)
            db.session.delete(hidden_category)
            db.session.commit()
            cache.clear()


def test_product_jsonld_is_valid_and_omits_unverified_claims(app):
    source = (REPO_ROOT / "app" / "loja" / "templates" / "loja" / "produto_detalhe.html").read_text(encoding="utf-8")
    marker = "{# ── DADOS ESTRUTURADOS FULL SNIPPET (PRODUTO) CORRIGIDO ── #}"
    fragment_start = source.index('<script type="application/ld+json">', source.index(marker))
    fragment_end = source.index("</script>", fragment_start) + len("</script>")
    fragment = source[fragment_start:fragment_end]
    produto = SimpleNamespace(
        nome_comercial="Produto de teste",
        nome="Produto interno de teste",
        fotos=[],
        foto_url="/static/img/produto-teste.jpg",
        descricao_comercial="<p>Descrição de teste.</p>",
        descricao=None,
        codigo="SEO-JSON-TESTE",
        marca_rel=None,
    )

    with app.test_request_context("/loja/produto/produto-de-teste"):
        html = app.jinja_env.from_string(fragment).render(
            produto=produto,
            precos={"preco_a_vista": 123.45},
            loja_canonical_url=canonical_store_url,
            gerar_link=lambda value: f"https://cdn.m4tatica.com.br/{value.lstrip('/')}",
        )

    raw_json = re.search(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL).group(1)
    structured_data = json.loads(raw_json)

    assert structured_data["@type"] == "Product"
    assert structured_data["offers"]["url"] == "https://loja.m4tatica.com.br/produto/produto-de-teste"
    assert structured_data["offers"]["price"] == "123.45"
    assert "aggregateRating" not in structured_data
    assert "availability" not in structured_data["offers"]
    assert "shippingDetails" not in structured_data["offers"]
    assert "hasMerchantReturnPolicy" not in structured_data["offers"]


def test_product_page_has_mobile_sticky_purchase_cta():
    source = (REPO_ROOT / "app" / "loja" / "templates" / "loja" / "produto_detalhe.html").read_text(encoding="utf-8")
    assert "produto-sticky-cta" in source
    assert "adicionarAoCarrinho({{ produto.id }}, this)" in source
    assert "@media (max-width: 991.98px)" in source
    assert "produto-sticky-cta d-lg-none" in source
    assert "inset: auto 0 0" not in source
    assert "env(safe-area-inset-bottom)" in source


def test_public_faq_page_has_visible_answers_metadata_and_official_sources(client):
    response = client.get("/loja/perguntas-frequentes")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<link rel="canonical" href="https://loja.m4tatica.com.br/perguntas-frequentes">' in html
    assert '"@type": "BreadcrumbList"' in html
    assert "Preciso de porte para comprar uma arma?" in html
    assert "Preciso de porte para comprar munição?" in html
    assert "A M4 Tática envia munições" in html
    assert "R$ 1.600,00 à vista" in html
    assert "https://www.gov.br/pf/pt-br/assuntos/armas/normativos/legislacao" in html
    assert "https://www.in.gov.br/en/web/dou/-/portaria-conjunta-c-ex/dg-pf-n-4-de-18-de-julho-de-2025-645587385" in html


def test_store_header_styles_do_not_apply_to_content_headers():
    base_source = (REPO_ROOT / "app" / "loja" / "templates" / "loja" / "base.html").read_text(encoding="utf-8")
    faq_source = (REPO_ROOT / "app" / "loja" / "templates" / "loja" / "perguntas_frequentes.html").read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", base_source, flags=re.DOTALL).group(1)

    assert ".store-header {" in style
    assert re.search(r"(?m)^\s*header\s*\{", style) is None
    assert '<header class="store-header">' in base_source
    assert '<header class="mb-4 mb-lg-5">' in faq_source


def test_contact_form_composes_whatsapp_message_instead_of_posting(client):
    response = client.get("/loja/fale-conosco")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="whatsapp-contact-form"' in html
    assert 'id="send-whatsapp-message"' in html
    assert "https://wa.me/" in html
    assert "new FormData(form)" in html
    assert "missingField.focus()" in html
    assert "window.open(url, '_blank')" in html
    assert 'name="csrf_token"' not in html
    assert 'method="POST"' not in html


def test_seo_templates_parse_without_jinja_syntax_errors(app):
    templates = [
        "loja/base.html",
        "loja/index.html",
        "loja/categoria.html",
        "loja/produto_detalhe.html",
        "loja/fale_conosco.html",
        "loja/perguntas_frequentes.html",
        "loja/pagina_institucional.html",
        "loja/links_uteis.html",
        "carrinho/sucesso.html",
    ]
    with app.app_context():
        for template_name in templates:
            app.jinja_env.get_template(template_name)
