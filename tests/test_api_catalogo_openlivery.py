from decimal import Decimal
from uuid import uuid4

from app import db
from app.produtos.models import Produto


API_KEY = "test-openlivery-catalog-token"
API_ROOT = "/api/v1/catalogo/produtos"


def _criar_produto(tag, *, visivel=True, nome=None):
    produto = Produto(
        codigo=f"API-{tag}",
        nome=nome or f"Produto API {tag}",
        nome_comercial=nome or f"Produto API {tag}",
        slug=f"produto-api-{tag}".lower(),
        visivel_loja=visivel,
        estoque_disponivel=7,
        requer_documentacao=True,
        preco_fornecedor=Decimal("40.00"),
        preco_final=Decimal("89.90"),
        custo_total=Decimal("12.00"),
        lucro_liquido_real=Decimal("77.00"),
        margem=Decimal("20.00"),
        descricao_comercial="Resumo do produto",
        descricao_longa="<p>Detalhe útil</p><script>alert('nao retornar')</script>",
        especificacoes_tecnicas={"cor": "preta", "material": "alumínio"},
    )
    db.session.add(produto)
    db.session.commit()
    return produto


def _headers():
    return {"Authorization": f"Bearer {API_KEY}"}


def test_api_falha_fechada_sem_chave_configurada(client, monkeypatch):
    monkeypatch.delenv("OPENLIVERY_CATALOG_API_KEY", raising=False)

    resposta = client.get(API_ROOT, query_string={"q": "lanterna"})

    assert resposta.status_code == 503
    assert resposta.get_json() == {"error": "integration_not_configured"}
    assert resposta.headers["Cache-Control"] == "private, no-store"


def test_api_rejeita_token_ausente_ou_incorreto(client, monkeypatch):
    monkeypatch.setenv("OPENLIVERY_CATALOG_API_KEY", API_KEY)

    sem_token = client.get(API_ROOT, query_string={"q": "lanterna"})
    token_incorreto = client.get(
        API_ROOT,
        query_string={"q": "lanterna"},
        headers={"Authorization": "Bearer token-incorreto"},
    )

    assert sem_token.status_code == 401
    assert token_incorreto.status_code == 401
    assert sem_token.headers["WWW-Authenticate"] == "Bearer"


def test_busca_autenticada_pagina_e_omite_campos_internos(client, monkeypatch):
    monkeypatch.setenv("OPENLIVERY_CATALOG_API_KEY", API_KEY)
    tag = uuid4().hex[:12]
    produtos = [_criar_produto(f"{tag}-{n}") for n in range(3)]
    oculto = _criar_produto(f"{tag}-oculto", visivel=False)

    resposta = client.get(
        API_ROOT,
        query_string={"q": tag, "page": 1, "per_page": 2},
        headers=_headers(),
    )

    assert resposta.status_code == 200
    body = resposta.get_json()
    assert len(body["products"]) == 2
    assert body["pagination"] == {"page": 1, "per_page": 2, "total": 3, "pages": 2}
    assert {item["slug"] for item in body["products"]}.issubset({p.slug for p in produtos})
    assert oculto.slug not in {item["slug"] for item in body["products"]}
    product = body["products"][0]
    assert product["price_brl"] == "89.90"
    assert product["availability"] == "in_stock"
    assert product["documentation_required"] is True
    assert not {"preco_fornecedor", "custo_total", "lucro_liquido_real", "margem", "estoque_disponivel"}.intersection(product)
    assert resposta.headers["Cache-Control"] == "private, no-store"
    assert all(not db.session.is_modified(item) for item in produtos)


def test_detalhe_retorna_descricao_e_especificacoes_sem_html_ativo(client, monkeypatch):
    monkeypatch.setenv("OPENLIVERY_CATALOG_API_KEY", API_KEY)
    tag = uuid4().hex[:12]
    produto = _criar_produto(tag)

    resposta = client.get(f"{API_ROOT}/{produto.slug}", headers=_headers())

    assert resposta.status_code == 200
    data = resposta.get_json()["product"]
    assert data["slug"] == produto.slug
    assert data["description"] == "Resumo do produto\n\nDetalhe útil"
    assert data["specifications"] == {"cor": "preta", "material": "alumínio"}
    assert "<p>" not in data["description"]
    assert "alert" not in data["description"]
    assert "estoque_disponivel" not in data


def test_detalhe_nao_expoe_produto_oculto(client, monkeypatch):
    monkeypatch.setenv("OPENLIVERY_CATALOG_API_KEY", API_KEY)
    produto = _criar_produto(uuid4().hex[:12], visivel=False)

    resposta = client.get(f"{API_ROOT}/{produto.slug}", headers=_headers())

    assert resposta.status_code == 404
    assert resposta.get_json() == {"error": "product_not_found"}


def test_busca_valida_limites_dos_parametros(client, monkeypatch):
    monkeypatch.setenv("OPENLIVERY_CATALOG_API_KEY", API_KEY)

    sem_termo = client.get(API_ROOT, query_string={"q": "x"}, headers=_headers())
    limite_pagina = client.get(
        API_ROOT,
        query_string={"q": "lanterna", "per_page": 21},
        headers=_headers(),
    )

    assert sem_termo.status_code == 400
    assert sem_termo.get_json()["error"] == "invalid_query"
    assert limite_pagina.status_code == 400
    assert limite_pagina.get_json()["error"] == "invalid_pagination"
