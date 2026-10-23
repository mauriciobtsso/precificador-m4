"""Authenticated, read-only product catalog API for trusted integrations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import hmac
import os
from urllib.parse import urljoin, urlparse

from flask import jsonify, request, url_for
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, object_session, subqueryload

from app import db
from app.catalog_api import catalog_api_bp
from app.extensions import limiter
from app.loja.routes import normalizar_foto_loja
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import CalibreProduto, MarcaProduto
from app.produtos.models import Produto

API_KEY_ENV = "OPENLIVERY_CATALOG_API_KEY"
MAX_QUERY_LENGTH = 120
MAX_PAGE_SIZE = 20


class _PlainTextParser(HTMLParser):
    """Extract readable description text and ignore script/style contents."""

    _BLOCK_TAGS = {"br", "div", "li", "p", "section", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _PlainTextParser()
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, AssertionError):
        return " ".join(value.split())
    return " ".join("".join(parser.parts).split())


def _authenticate() -> tuple[dict | None, int | None, dict[str, str] | None]:
    expected = os.getenv(API_KEY_ENV, "").strip()
    if not expected:
        return {"error": "integration_not_configured"}, 503, None

    scheme, separator, supplied = request.headers.get("Authorization", "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not supplied.strip():
        return {"error": "unauthorized"}, 401, {"WWW-Authenticate": "Bearer"}
    if not hmac.compare_digest(supplied.strip(), expected):
        return {"error": "unauthorized"}, 401, {"WWW-Authenticate": "Bearer"}
    return None, None, None


def _auth_required():
    payload, status, headers = _authenticate()
    if payload is not None:
        response = jsonify(payload)
        if headers:
            response.headers.update(headers)
        return response, status
    return None


def _positive_int(name: str, default: int, maximum: int | None = None) -> int | None:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 1 or (maximum is not None and value > maximum):
        return None
    return value


def _query_pattern(token: str) -> str:
    escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _build_search_query(query, search: str):
    fields = (
        Produto.nome,
        Produto.nome_comercial,
        Produto.codigo,
        Produto.tags_palavras_chave,
        Produto.descricao_comercial,
    )
    for token in search.split()[:8]:
        pattern = _query_pattern(token)
        conditions = [field.ilike(pattern, escape="\\") for field in fields]
        conditions.extend(
            (
                Produto.marca_rel.has(MarcaProduto.nome.ilike(pattern, escape="\\")),
                Produto.categoria.has(CategoriaProduto.nome.ilike(pattern, escape="\\")),
                Produto.calibre_rel.has(CalibreProduto.nome.ilike(pattern, escape="\\")),
            )
        )
        query = query.filter(or_(*conditions))
    return query


def _current_public_price(product: Produto) -> tuple[str, bool]:
    """Use the storefront pricing rules without leaving a GET-side DB change."""
    session = object_session(product)
    if session is None:
        pricing = product.calcular_precos()
    else:
        with session.no_autoflush:
            pricing = product.calcular_precos()
        # calcular_precos() updates cached model attributes. Discard those
        # in-memory changes so this read-only endpoint never flushes them.
        session.expire(product, ["custo_total", "preco_a_vista", "lucro_liquido_real"])

    try:
        amount = Decimal(str(pricing.get("preco_a_vista", 0))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0.00")
    return format(amount, ".2f"), bool(pricing.get("em_oferta"))


def _absolute_image_url(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalizar_foto_loja(value)
    parsed = urlparse(normalized)
    if parsed.scheme:
        return normalized if parsed.scheme == "https" else None
    return urljoin(request.url_root, normalized.lstrip("/"))


def _product_url(product: Produto) -> str | None:
    if not product.slug:
        return None
    return url_for("loja.detalhe_produto", slug=product.slug, _external=True)


def _serialize_product(product: Produto, *, detail: bool = False) -> dict:
    price, promotion_active = _current_public_price(product)
    stock = product.estoque_disponivel
    availability = "unknown" if stock is None else ("in_stock" if stock > 0 else "out_of_stock")
    image = _absolute_image_url(product.foto_url)

    result = {
        "id": product.id,
        "code": product.codigo,
        "name": product.nome_comercial or product.nome,
        "slug": product.slug,
        "category": product.categoria.nome if product.categoria else None,
        "brand": product.marca_rel.nome if product.marca_rel else None,
        "price_brl": price,
        "promotion_active": promotion_active,
        "availability": availability,
        "documentation_required": bool(product.requer_documentacao),
        "image_url": image,
        "product_url": _product_url(product),
    }
    if detail:
        description_parts = []
        for source in (product.descricao_comercial, product.descricao_longa):
            text = _plain_text(source)
            if text and text not in description_parts:
                description_parts.append(text)
        description = "\n\n".join(description_parts)
        technical_details = dict(product.especificacoes_tecnicas or {})
        if product.calibre_rel:
            technical_details.setdefault("caliber", product.calibre_rel.nome)
        if product.tipo_rel:
            technical_details.setdefault("type", product.tipo_rel.nome)
        if product.funcionamento_rel:
            technical_details.setdefault("operation", product.funcionamento_rel.nome)

        images = []
        seen: set[str] = set()
        for photo in product.fotos:
            photo_url = _absolute_image_url(photo.url)
            if photo_url and photo_url not in seen:
                seen.add(photo_url)
                images.append(photo_url)
        if image and image not in seen:
            images.insert(0, image)

        result.update(
            {
                "description": description,
                "specifications": technical_details,
                "images": images,
            }
        )
    return result


def _loadable_products():
    return Produto.query.options(
        joinedload(Produto.categoria),
        joinedload(Produto.marca_rel),
        joinedload(Produto.calibre_rel),
        joinedload(Produto.tipo_rel),
        joinedload(Produto.funcionamento_rel),
        subqueryload(Produto.fotos),
    )


@catalog_api_bp.after_request
def _secure_api_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-API-Version"] = "1"
    return response


@catalog_api_bp.get("/produtos")
@limiter.limit("120 per minute")
def listar_produtos():
    denied = _auth_required()
    if denied:
        return denied

    search = request.args.get("q", "").strip()
    if len(search) < 2 or len(search) > MAX_QUERY_LENGTH:
        return jsonify({"error": "invalid_query", "message": "Informe q com 2 a 120 caracteres."}), 400

    page = _positive_int("page", 1)
    per_page = _positive_int("per_page", 10, MAX_PAGE_SIZE)
    if page is None or per_page is None:
        return jsonify({"error": "invalid_pagination", "message": "page deve ser positivo e per_page deve estar entre 1 e 20."}), 400

    query = _loadable_products().filter(Produto.visivel_loja.is_(True))
    query = _build_search_query(query, search)
    pagination = query.order_by(func.coalesce(Produto.nome_comercial, Produto.nome).asc(), Produto.id.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify(
        {
            "products": [_serialize_product(product) for product in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            },
        }
    )


@catalog_api_bp.get("/produtos/<string:slug>")
@limiter.limit("120 per minute")
def obter_produto(slug: str):
    denied = _auth_required()
    if denied:
        return denied

    product = _loadable_products().filter(
        Produto.slug == slug,
        Produto.visivel_loja.is_(True),
    ).first()
    if product is None:
        return jsonify({"error": "product_not_found"}), 404
    return jsonify({"product": _serialize_product(product, detail=True)})
