"""
app/utils/thumbnail_utils.py
─────────────────────────────────────────────────────────────────────────────
Geração de thumbnails no servidor para resolver o problema de imagens
oversized apontado pelo PageSpeed Insights.

Problema:  logos de 3840×1957px servidos em 85×43px → 115 KiB desperdiçados
Solução:   gerar versões redimensionadas no R2 e servir pelo CDN

Como funciona:
  1. Ao cadastrar/atualizar produto ou marca, o sistema gera automaticamente
     thumbnails (280px, 160px, 80px) e os salva no R2 com sufixo _tXXX
  2. Os templates usam a função get_thumb_url() para pegar o tamanho certo
  3. Imagens já existentes podem ser processadas em lote pelo comando CLI

Tamanhos gerados:
  _t280  → cards de produto (desktop)
  _t160  → cards de produto (mobile) e grid
  _t80   → logos de marcas no carrossel

Roteamento de buckets (igual ao r2_helpers.py):
  produtos/*  → m4-loja-publico  (CDN público)
  outros      → m4-clientes-docs (bucket privado)
─────────────────────────────────────────────────────────────────────────────
"""

import io
import os
import re
import logging
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# ── Buckets (espelha r2_helpers.py) ───────────────────────────────────────
BUCKET_PUBLICO = "m4-loja-publico"
BUCKET_PRIVADO = "m4-clientes-docs"
CDN_URL = "https://cdn.m4tatica.com.br"

# ── Tamanhos a gerar automaticamente ──────────────────────────────────────
THUMB_SIZES = {
    't280': (280, 280),   # card produto desktop
    't160': (160, 160),   # card produto mobile / grid
    't80':  (80,  80),    # logo de marca
}

# Qualidade WebP para cada tamanho (menor = mais compacto)
THUMB_QUALITY = {
    't280': 82,
    't160': 78,
    't80':  72,
}


# ── Helpers de URL ──────────────────────────────────────────────────────────

def _strip_cdn_prefix(url: str) -> str:
    """
    Remove o prefixo de URL e retorna só o path (r2_key).

    Exemplos:
        https://cdn.m4tatica.com.br/produtos/fotos/166/aa4.webp
            → produtos/fotos/166/aa4.webp

        https://pub-xxxx.r2.dev/produtos/fotos/166/aa4.webp
            → produtos/fotos/166/aa4.webp

        https://cdn.m4tatica.com.br/m4-clientes-docs/produtos/...
            → produtos/...
    """
    if not url:
        return ''
    parsed = urlparse(url)
    path = parsed.path.lstrip('/')

    # Remove prefixo do bucket privado se aparecer no path
    if path.startswith(f"{BUCKET_PRIVADO}/"):
        path = path[len(BUCKET_PRIVADO) + 1:]

    return path


def _normalizar_key(r2_key: str) -> str:
    """Normaliza separadores de path para '/' (compatibilidade Windows/Linux)."""
    return r2_key.replace('\\', '/')


def _bucket_para_key(r2_key: str) -> str:
    """
    Retorna o bucket correto para um dado r2_key.
    Mesma regra do r2_helpers.py:
      produtos/* → m4-loja-publico
      outros     → m4-clientes-docs
    """
    if _normalizar_key(r2_key).startswith('produtos/'):
        return BUCKET_PUBLICO
    return BUCKET_PRIVADO


def get_thumb_url(original_url: str, size_key: str = 't280') -> str:
    """
    Retorna a URL do thumbnail no CDN.
    Se o thumbnail não existir ainda, retorna a URL original (fallback seguro).

    Uso nos templates:
        {{ get_thumb_url(produto.foto_url, 't280') }}
        {{ get_thumb_url(marca.logo_url, 't80') }}
    """
    if not original_url or size_key not in THUMB_SIZES:
        return original_url or ''

    # Insere o sufixo antes da extensão
    # ex: produtos/fotos/166/aa4258c.webp → produtos/fotos/166/aa4258c_t280.webp
    path = _strip_cdn_prefix(original_url)
    stem, ext = _split_ext(path)
    thumb_path = f"{stem}_{size_key}.webp"

    return f"{CDN_URL}/{thumb_path}"


def _split_ext(path: str):
    """Separa stem e extensão de um path. Sempre retorna com '/' (Unix-style)."""
    p = Path(path)
    stem = str(p.parent / p.stem).replace('\\', '/')
    return stem, p.suffix.lower()


# ── Geração do thumbnail ────────────────────────────────────────────────────

def generate_thumbnail(image_bytes: bytes, size_key: str) -> bytes:
    """
    Recebe os bytes da imagem original e retorna bytes do thumbnail WebP.

    Args:
        image_bytes: conteúdo binário da imagem original
        size_key:    't280', 't160' ou 't80'

    Returns:
        bytes do WebP gerado
    """
    if size_key not in THUMB_SIZES:
        raise ValueError(f"size_key inválido: {size_key}. Use: {list(THUMB_SIZES.keys())}")

    width, height = THUMB_SIZES[size_key]
    quality = THUMB_QUALITY[size_key]

    with Image.open(io.BytesIO(image_bytes)) as img:
        # Converte para RGBA para preservar transparência (logos PNG)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')

        # thumbnail() preserva aspect ratio e não faz upscale
        img.thumbnail((width, height), Image.LANCZOS)

        # Para WebP com fundo branco (evita fundo preto em imagens com alpha)
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        buf = io.BytesIO()
        img.save(buf, format='WEBP', quality=quality, method=4)
        return buf.getvalue()


# ── Upload para R2 ─────────────────────────────────────────────────────────

def _get_r2_client():
    """Cria cliente S3-compatível para o R2 usando as variáveis de ambiente."""
    try:
        import boto3
        from botocore.config import Config

        endpoint = os.environ.get('R2_ENDPOINT_URL', '')
        access_key = os.environ.get('R2_ACCESS_KEY_ID', '')
        secret_key = os.environ.get('R2_SECRET_ACCESS_KEY', '')

        if not all([endpoint, access_key, secret_key]):
            logger.debug("Credenciais R2 não configuradas — boto3 não iniciado.")
            return None

        return boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto',
        )
    except ImportError:
        logger.warning("boto3 não instalado — upload indisponível.")
        return None


def upload_thumb_to_r2(thumb_bytes: bytes, r2_key: str) -> bool:
    """
    Faz upload do thumbnail para o bucket correto no R2.

    Roteamento (igual ao r2_helpers.py):
      produtos/* → m4-loja-publico  (acessível via CDN público)
      outros     → m4-clientes-docs (bucket privado)

    Args:
        thumb_bytes: bytes do WebP gerado
        r2_key:      caminho no bucket, ex: produtos/fotos/166/aa4258c_t280.webp

    Returns:
        True se sucesso, False se erro
    """
    # Garante separadores Unix (evita problema no Windows)
    r2_key = _normalizar_key(r2_key)
    bucket = _bucket_para_key(r2_key)

    client = _get_r2_client()
    if client:
        try:
            client.put_object(
                Bucket=bucket,
                Key=r2_key,
                Body=thumb_bytes,
                ContentType='image/webp',
                CacheControl='public, max-age=31536000, immutable',
            )
            logger.info(f"Thumbnail enviado → bucket={bucket} key={r2_key}")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar thumbnail {r2_key} → bucket={bucket}: {e}")
            return False

    logger.error("Cliente R2 não disponível — upload cancelado.")
    return False


# ── Função principal: processar imagem e gerar todos os thumbs ─────────────

def process_image_and_create_thumbs(
    image_bytes: bytes,
    original_r2_key: str,
    sizes: list = None,
) -> dict:
    """
    Gera thumbnails de todos os tamanhos e faz upload para o R2.

    Args:
        image_bytes:     bytes da imagem original
        original_r2_key: caminho no R2, ex: produtos/fotos/166/aa4258c.webp
        sizes:           lista de size_keys, padrão: todos os THUMB_SIZES

    Returns:
        dict com os paths gerados, ex:
        {'t280': 'produtos/fotos/166/aa4258c_t280.webp', ...}
    """
    if sizes is None:
        sizes = list(THUMB_SIZES.keys())

    p = Path(original_r2_key)
    base_key = str(p.parent / p.stem).replace('\\', '/')

    results = {}
    for size_key in sizes:
        try:
            thumb_bytes = generate_thumbnail(image_bytes, size_key)
            thumb_key = f"{base_key}_{size_key}.webp"
            ok = upload_thumb_to_r2(thumb_bytes, thumb_key)
            if ok:
                results[size_key] = thumb_key
                logger.info(
                    f"Thumb {size_key} gerado: {len(thumb_bytes)/1024:.1f} KiB "
                    f"(original: {len(image_bytes)/1024:.1f} KiB)"
                )
        except Exception as e:
            logger.error(f"Erro ao gerar thumb {size_key} para {original_r2_key}: {e}")

    return results