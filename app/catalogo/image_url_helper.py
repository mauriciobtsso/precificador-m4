"""
app/catalogo/image_url_helper.py
─────────────────────────────────────────────────────────────────────────────
Helper para converter URLs de imagens do CDN para o proxy com fallback.

Uso nos templates:
    {{ convert_image_url(produto.foto_url) }}
    {{ convert_image_url(marca.logo_url, 't80') }}

Função também disponível no contexto do template automaticamente.
─────────────────────────────────────────────────────────────────────────────
"""

from urllib.parse import urlparse, quote
from flask import url_for


def convert_image_url(cdn_url: str, size_key: str = None) -> str:
    """
    Converte uma URL de imagem do CDN para o proxy com fallback.
    
    Exemplos:
        Input:  https://cdn.m4tatica.com.br/produtos/fotos/166/aa4.webp
        Output: /catalogo/image-proxy/produtos/fotos/166/aa4.webp
        
        Input:  https://cdn.m4tatica.com.br/produtos/fotos/166/aa4_t280.webp
        Output: /catalogo/image-proxy/produtos/fotos/166/aa4_t280.webp
    
    Args:
        cdn_url: URL completa da imagem no CDN ou path relativo
        size_key: (opcional) sufixo de tamanho, ex: 't280', 't160'
    
    Returns:
        URL do proxy, ex: /catalogo/image-proxy/produtos/fotos/166/aa4.webp
    """
    
    if not cdn_url:
        return ''
    
    # Extrai o path da URL
    if cdn_url.startswith('http'):
        parsed = urlparse(cdn_url)
        image_path = parsed.path.lstrip('/')
    else:
        image_path = cdn_url.lstrip('/')
    
    # Remove prefixos de bucket se existirem
    for bucket in ('m4-loja-publico', 'm4-clientes-docs'):
        if image_path.startswith(bucket + '/'):
            image_path = image_path[len(bucket) + 1:]
            break
    
    # Se size_key foi fornecido e a URL não contém o sufixo, adiciona
    if size_key and f'_{size_key}' not in image_path:
        # Insere o sufixo antes da extensão
        if '.' in image_path:
            parts = image_path.rsplit('.', 1)
            image_path = f"{parts[0]}_{size_key}.{parts[1]}"
        else:
            image_path = f"{image_path}_{size_key}"
    
    # Retorna URL do proxy
    return f"/catalogo/image-proxy/{image_path}"


def convert_thumb_url(original_url: str, size_key: str = 't280') -> str:
    """
    Atalho para converter URLs de thumbnails.
    
    Equivalente a: convert_image_url(original_url, size_key)
    
    Uso:
        {{ convert_thumb_url(produto.foto_url, 't280') }}
    """
    return convert_image_url(original_url, size_key)
