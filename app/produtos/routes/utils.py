# app/produtos/routes/utils.py
import os
import uuid
import mimetypes
import boto3
from urllib.parse import urlparse
from flask import current_app

# Buckets
BUCKET_PUBLICO = "m4-loja-publico"
BUCKET_PRIVADO = "m4-clientes-docs"


def _r2_client():
    """Inicializa o cliente S3 (R2) lendo variáveis do .env ou do app.config"""
    endpoint = current_app.config.get("R2_ENDPOINT_URL") or os.getenv("R2_ENDPOINT_URL")
    access_key = current_app.config.get("R2_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID")
    secret_key = current_app.config.get("R2_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY")
    region = current_app.config.get("R2_REGION_NAME") or "auto"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def _r2_bucket():
    """Obtém o nome do bucket R2 (Documentos/Privado)."""
    return (
        current_app.config.get("R2_BUCKET")
        or current_app.config.get("R2_BUCKET_NAME")
        or os.getenv("R2_BUCKET_NAME")
    )


def _r2_bucket_publico():
    """Retorna explicitamente o bucket da LOJA (Público/Fotos de Produtos)."""
    return BUCKET_PUBLICO


def _r2_public_base():
    """
    Base pública para montar URL acessível no R2.
    Prioriza variável .env R2_PUBLIC_BASE_URL (ex: https://cdn.m4tatica.com.br)
    """
    return (
        current_app.config.get("R2_PUBLIC_BASEURL")
        or current_app.config.get("R2_PUBLIC_BASE_URL")
        or os.getenv("R2_PUBLIC_BASE_URL")
    )


def _guess_ext(filename_or_mime: str) -> str:
    """Tenta determinar a extensão com base no MIME type ou nome do arquivo."""
    if not filename_or_mime:
        return ".jpg"
    try:
        if "/" in filename_or_mime:
            ext = mimetypes.guess_extension(filename_or_mime)
        else:
            ext = mimetypes.guess_extension(
                mimetypes.guess_type(filename_or_mime)[0] or ""
            )
        return (ext or ".jpg").lower()
    except Exception:
        return ".jpg"


def _key_from_url(public_url: str | None) -> str | None:
    """
    Extrai o r2_key limpo a partir de qualquer formato de URL ou path salvo no banco.

    Exemplos:
      https://cdn.m4tatica.com.br/produtos/fotos/5/abc.webp        → produtos/fotos/5/abc.webp
      https://xxx.r2.dev/m4-loja-publico/produtos/fotos/5/abc.webp → produtos/fotos/5/abc.webp
      https://xxx.r2.dev/m4-clientes-docs/docs/abc.pdf             → docs/abc.pdf
      produtos/fotos/5/abc.webp                                    → produtos/fotos/5/abc.webp
    """
    if not public_url:
        return None
    try:
        parsed = urlparse(public_url)
        key = parsed.path.lstrip("/")

        # ✅ Remove prefixo do bucket privado se estiver no path
        if key.startswith(BUCKET_PRIVADO + "/"):
            key = key[len(BUCKET_PRIVADO) + 1:]

        # ✅ Remove prefixo do bucket público se estiver no path (BUG CORRIGIDO)
        if key.startswith(BUCKET_PUBLICO + "/"):
            key = key[len(BUCKET_PUBLICO) + 1:]

        return key if key else None
    except Exception:
        return None