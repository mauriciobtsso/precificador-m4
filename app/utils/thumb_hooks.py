"""
app/utils/thumb_hooks.py
─────────────────────────────────────────────────────────────────────────────
Hooks SQLAlchemy para gerar thumbnails automaticamente sempre que
uma imagem nova for salva em Produto ou MarcaProduto.

Como integrar:

1. No arquivo onde você define o modelo Produto, adicione no final:
       from app.utils.thumb_hooks import registrar_hooks
       registrar_hooks()

   Ou em app/__init__.py, após create_app():
       from app.utils.thumb_hooks import registrar_hooks
       registrar_hooks()

2. O hook só dispara quando foto_url ou logo_url mudar — não há impacto
   em saves que não alteram imagem.
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import threading
from sqlalchemy import event

logger = logging.getLogger(__name__)

_hooks_registered = False


def _gerar_thumbs_async(image_url: str, cdn_base: str):
    """
    Gera thumbnails em thread separada para não bloquear o request.
    """
    import urllib.request
    from app.utils.thumbnail_utils import (
        generate_thumbnail, upload_thumb_to_r2, _strip_cdn_prefix
    )
    from pathlib import Path

    # Garante URL completa
    if not image_url.startswith('http'):
        image_url = f"{cdn_base}/{image_url.lstrip('/')}"

    try:
        req = urllib.request.Request(
            image_url,
            headers={'User-Agent': 'M4Tatica-ThumbGen/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            image_bytes = resp.read()
    except Exception as e:
        logger.warning(f"thumb_hook: não foi possível baixar {image_url}: {e}")
        return

    r2_key = _strip_cdn_prefix(image_url)
    p = Path(r2_key)
    base_key = str(p.parent / p.stem)

    # Define tamanhos baseado no path
    if 'logos' in r2_key or 'marcas' in r2_key:
        sizes = ['t80']
    else:
        sizes = ['t280', 't160']

    for size_key in sizes:
        try:
            thumb_bytes = generate_thumbnail(image_bytes, size_key)
            thumb_key = f"{base_key}_{size_key}.webp"
            ok = upload_thumb_to_r2(thumb_bytes, thumb_key)
            if ok:
                orig_kb = len(image_bytes) / 1024
                thumb_kb = len(thumb_bytes) / 1024
                logger.info(
                    f"thumb_hook ✓ {size_key}: "
                    f"{orig_kb:.0f} KiB → {thumb_kb:.0f} KiB"
                )
        except Exception as e:
            logger.error(f"thumb_hook ✗ {size_key} para {r2_key}: {e}")


def _disparar_thumb(instance, url_field: str):
    """Dispara geração de thumb em background se a URL mudou."""
    import os
    cdn_base = os.environ.get('CDN_BASE_URL', 'https://cdn.m4tatica.com.br')

    url = getattr(instance, url_field, None)
    if not url:
        return

    t = threading.Thread(
        target=_gerar_thumbs_async,
        args=(url, cdn_base),
        daemon=True,
    )
    t.start()


def registrar_hooks():
    """
    Registra os event listeners nos modelos.
    Chame uma única vez na inicialização do app.
    """
    global _hooks_registered
    if _hooks_registered:
        return

    try:
        from app.produtos.models import Produto
        from app.produtos.configs.models import MarcaProduto

        @event.listens_for(Produto, 'after_insert')
        def after_produto_insert(mapper, connection, target):
            if target.foto_url:
                _disparar_thumb(target, 'foto_url')

        @event.listens_for(Produto, 'after_update')
        def after_produto_update(mapper, connection, target):
            # Só dispara se foto_url realmente mudou
            from sqlalchemy import inspect
            hist = inspect(target).attrs.foto_url.history
            if hist.has_changes() and target.foto_url:
                _disparar_thumb(target, 'foto_url')

        @event.listens_for(MarcaProduto, 'after_insert')
        def after_marca_insert(mapper, connection, target):
            if target.logo_url:
                _disparar_thumb(target, 'logo_url')

        @event.listens_for(MarcaProduto, 'after_update')
        def after_marca_update(mapper, connection, target):
            from sqlalchemy import inspect
            hist = inspect(target).attrs.logo_url.history
            if hist.has_changes() and target.logo_url:
                _disparar_thumb(target, 'logo_url')

        _hooks_registered = True
        logger.info("thumb_hooks: listeners registrados para Produto e MarcaProduto")

    except ImportError as e:
        logger.warning(f"thumb_hooks: não foi possível registrar hooks: {e}")