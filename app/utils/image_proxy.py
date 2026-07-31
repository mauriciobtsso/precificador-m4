"""
app/utils/image_proxy.py
─────────────────────────────────────────────────────────────────────────────
Proxy de Conversão On-the-Fly para Compatibilidade WebP em Navegadores Antigos

Problema: iPad Mini 1ª geração com iOS 9.3.6 não suporta WebP.

Solução: Criar um endpoint que detecta o suporte a WebP via cabeçalho Accept
e converte a imagem para JPEG se necessário, com caching para performance.

Fluxo:
  1. Cliente requisita /catalogo/image-proxy/produtos/fotos/166/aa4.webp
  2. Proxy verifica Accept header
  3. Se não suporta WebP, baixa a imagem do CDN e converte para JPEG
  4. Resultado é cacheado para próximas requisições
  5. Imagem é servida ao cliente
─────────────────────────────────────────────────────────────────────────────
"""

import io
import logging
import hashlib
from urllib.parse import quote
from pathlib import Path

import requests
from PIL import Image
from flask import current_app, send_file, request
from werkzeug.exceptions import BadRequest, NotFound

logger = logging.getLogger(__name__)

# Configurações
CDN_URL = "https://cdn.m4tatica.com.br"
CACHE_TIMEOUT = 86400 * 30  # 30 dias
SUPPORTED_FORMATS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'avif'}
FALLBACK_FORMAT = 'jpeg'  # Formato para conversão em navegadores antigos


def _accepts_webp(accept_header: str) -> bool:
    """
    Verifica se o cliente aceita WebP analisando o cabeçalho Accept.
    
    Exemplos:
        "image/webp,image/*,*/*;q=0.8" → True
        "image/jpeg,image/png" → False
        "" → False
    """
    if not accept_header:
        return False
    return 'image/webp' in accept_header.lower()


def _get_cache_key(image_path: str, output_format: str) -> str:
    """
    Gera uma chave de cache baseada no path da imagem e formato de saída.
    
    Args:
        image_path: caminho da imagem, ex: "produtos/fotos/166/aa4.webp"
        output_format: formato de saída, ex: "jpeg"
    
    Returns:
        chave de cache única, ex: "img_cache_abc123def456"
    """
    cache_str = f"{image_path}:{output_format}"
    hash_digest = hashlib.md5(cache_str.encode()).hexdigest()[:12]
    return f"img_cache_{hash_digest}"


def _download_image_from_cdn(image_path: str) -> bytes:
    """
    Baixa a imagem do CDN.
    
    Args:
        image_path: caminho da imagem no CDN, ex: "produtos/fotos/166/aa4.webp"
    
    Returns:
        bytes da imagem
    
    Raises:
        NotFound: se a imagem não existir no CDN
        Exception: se houver erro na requisição
    """
    url = f"{CDN_URL}/{image_path.lstrip('/')}"
    
    try:
        logger.info(f"[IMAGE_PROXY] Baixando imagem do CDN: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            logger.warning(f"[IMAGE_PROXY] Imagem não encontrada no CDN: {url}")
            raise NotFound(f"Imagem não encontrada: {image_path}")
        
        response.raise_for_status()
        return response.content
    
    except requests.RequestException as e:
        logger.error(f"[IMAGE_PROXY] Erro ao baixar imagem do CDN {url}: {e}")
        raise


def _convert_image_format(image_bytes: bytes, output_format: str = 'jpeg') -> bytes:
    """
    Converte imagem para o formato especificado.
    
    Args:
        image_bytes: bytes da imagem original
        output_format: formato de saída ('jpeg', 'png', etc.)
    
    Returns:
        bytes da imagem convertida
    
    Raises:
        ValueError: se o formato não for suportado
    """
    if output_format.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Formato não suportado: {output_format}")
    
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Converte para RGB se necessário (para JPEG)
            if output_format.lower() in ('jpeg', 'jpg'):
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Cria fundo branco para imagens com transparência
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            
            # Salva em memória
            buf = io.BytesIO()
            save_kwargs = {'format': output_format.upper()}
            
            # Otimizações por formato
            if output_format.lower() in ('jpeg', 'jpg'):
                save_kwargs['quality'] = 85
                save_kwargs['optimize'] = True
            elif output_format.lower() == 'png':
                save_kwargs['optimize'] = True
            
            img.save(buf, **save_kwargs)
            buf.seek(0)
            return buf.getvalue()
    
    except Exception as e:
        logger.error(f"[IMAGE_PROXY] Erro ao converter imagem para {output_format}: {e}")
        raise


def get_image_with_fallback(image_path: str, accept_header: str = '') -> tuple:
    """
    Retorna a imagem com fallback automático para JPEG se necessário.
    
    Fluxo:
      1. Se cliente aceita WebP, retorna a URL original do CDN (sem proxy)
      2. Se não aceita, baixa a imagem, converte para JPEG e cachea
    
    Args:
        image_path: caminho da imagem, ex: "produtos/fotos/166/aa4.webp"
        accept_header: cabeçalho Accept da requisição
    
    Returns:
        tuple (image_bytes, content_type, output_format)
    """
    
    # Se cliente aceita WebP, retorna URL original (sem conversão)
    if _accepts_webp(accept_header):
        logger.debug(f"[IMAGE_PROXY] Cliente suporta WebP: {image_path}")
        url = f"{CDN_URL}/{image_path.lstrip('/')}"
        return url, 'image/webp', 'webp'
    
    # Cliente não suporta WebP → converter para JPEG
    logger.info(f"[IMAGE_PROXY] Cliente não suporta WebP, convertendo: {image_path}")
    
    output_format = FALLBACK_FORMAT
    cache_key = _get_cache_key(image_path, output_format)
    
    # Tenta recuperar do cache
    try:
        cache = current_app.extensions.get('cache')
        
        if cache:
            cached_image = cache.get(cache_key)
            if cached_image:
                logger.info(f"[IMAGE_PROXY] Imagem recuperada do cache: {cache_key}")
                return cached_image, f'image/{output_format}', output_format
    except Exception as e:
        logger.warning(f"[IMAGE_PROXY] Erro ao acessar cache: {e}")
    
    # Não estava em cache → baixar e converter
    try:
        image_bytes = _download_image_from_cdn(image_path)
        converted_bytes = _convert_image_format(image_bytes, output_format)
        
        # Armazena no cache
        try:
            cache = current_app.extensions.get('cache')
            if cache:
                cache.set(cache_key, converted_bytes, timeout=CACHE_TIMEOUT)
                logger.info(f"[IMAGE_PROXY] Imagem cacheada: {cache_key}")
        except Exception as e:
            logger.warning(f"[IMAGE_PROXY] Erro ao cachear imagem: {e}")
        
        return converted_bytes, f'image/{output_format}', output_format
    
    except Exception as e:
        logger.error(f"[IMAGE_PROXY] Erro ao processar imagem {image_path}: {e}")
        raise


def serve_image_with_fallback(image_path: str) -> any:
    """
    Endpoint Flask que serve a imagem com fallback automático.
    
    Uso em routes.py:
        @catalogo_bp.route('/image-proxy/<path:image_path>')
        def image_proxy(image_path):
            return serve_image_with_fallback(image_path)
    
    Args:
        image_path: caminho da imagem, ex: "produtos/fotos/166/aa4.webp"
    
    Returns:
        Response Flask com a imagem
    """
    
    # Validação básica
    if not image_path:
        raise BadRequest("Caminho da imagem não fornecido")
    
    # Previne directory traversal
    if '..' in image_path or image_path.startswith('/'):
        raise BadRequest("Caminho inválido")
    
    accept_header = request.headers.get('Accept', '')
    
    try:
        result = get_image_with_fallback(image_path, accept_header)
        
        # Se for URL (cliente suporta WebP), redireciona
        if isinstance(result[0], str):
            from flask import redirect
            return redirect(result[0], code=307)
        
        # Se for bytes (cliente não suporta WebP), serve a imagem convertida
        image_bytes, content_type, output_format = result
        
        return send_file(
            io.BytesIO(image_bytes),
            mimetype=content_type,
            as_attachment=False,
            download_name=f"image.{output_format}"
        )
    
    except NotFound:
        logger.warning(f"[IMAGE_PROXY] Imagem não encontrada: {image_path}")
        raise
    except Exception as e:
        logger.error(f"[IMAGE_PROXY] Erro ao servir imagem: {e}")
        raise
