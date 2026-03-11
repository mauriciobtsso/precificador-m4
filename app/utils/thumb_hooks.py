"""
app/utils/thumb_hooks.py
─────────────────────────────────────────────────────────────────────────────
Hooks SQLAlchemy para gerar thumbnails automaticamente.
Atualizado para buscar bytes via Boto3 e rodar dentro do Application Context.
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import threading
from sqlalchemy import event

logger = logging.getLogger(__name__)

_hooks_registered = False

def _baixar_imagem_boto3(image_url: str):
    """
    Baixa a imagem diretamente do R2 via Boto3, evitando o erro 401 de URL.
    """
    from app.produtos.routes.utils import _r2_client, _r2_bucket_publico, _r2_bucket, _key_from_url
    
    key = _key_from_url(image_url)
    if not key:
        return None

    client = _r2_client()
    
    # 1. Tenta no público
    try:
        response = client.get_object(Bucket=_r2_bucket_publico(), Key=key)
        return response['Body'].read()
    except Exception:
        pass
        
    # 2. Tenta no privado
    try:
        response = client.get_object(Bucket=_r2_bucket(), Key=key)
        return response['Body'].read()
    except Exception as e:
        logger.error(f"thumb_hook: Falha ao baixar {key} via Boto3: {e}")
        return None

def _gerar_thumbs_async(app, image_url: str, cdn_base: str):
    """Gera thumbnails em thread separada DENTRO DO CONTEXTO DO FLASK."""
    with app.app_context():
        from app.utils.thumbnail_utils import (
            generate_thumbnail, upload_thumb_to_r2, _strip_cdn_prefix
        )
        from pathlib import Path

        # Baixa a imagem com as credenciais do servidor (blindado contra 401)
        image_bytes = _baixar_imagem_boto3(image_url)
        if not image_bytes:
            logger.warning(f"thumb_hook: não foi possível obter bytes da imagem: {image_url}")
            return

        r2_key = _strip_cdn_prefix(image_url)
        p = Path(r2_key)
        base_key = str(p.parent / p.stem)

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
                    logger.info(f"thumb_hook ✓ {size_key} gerado com sucesso.")
            except Exception as e:
                logger.error(f"thumb_hook ✗ erro em {size_key} para {r2_key}: {e}")

def _disparar_thumb(instance, url_field: str):
    import os
    from flask import current_app
    
    cdn_base = os.environ.get('CDN_BASE_URL', 'https://cdn.m4tatica.com.br')
    url = getattr(instance, url_field, None)
    if not url: return

    # Pega a instância real do app para passar para a thread
    app = current_app._get_current_object()

    t = threading.Thread(
        target=_gerar_thumbs_async,
        args=(app, url, cdn_base),
        daemon=True,
    )
    t.start()

def registrar_hooks():
    global _hooks_registered
    if _hooks_registered: return

    try:
        from app.produtos.models import Produto
        from app.produtos.configs.models import MarcaProduto

        @event.listens_for(Produto, 'after_insert')
        def after_produto_insert(mapper, connection, target):
            if target.foto_url: _disparar_thumb(target, 'foto_url')

        @event.listens_for(Produto, 'after_update')
        def after_produto_update(mapper, connection, target):
            from sqlalchemy import inspect
            hist = inspect(target).attrs.foto_url.history
            if hist.has_changes() and target.foto_url:
                _disparar_thumb(target, 'foto_url')

        @event.listens_for(MarcaProduto, 'after_insert')
        def after_marca_insert(mapper, connection, target):
            if target.logo_url: _disparar_thumb(target, 'logo_url')

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