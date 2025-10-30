import os
import uuid
import mimetypes
import boto3
from urllib.parse import urlparse
from flask import current_app

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
    """Obtém o nome do bucket R2 (compatível com .env e config local)."""
    return (
        current_app.config.get("R2_BUCKET")
        or current_app.config.get("R2_BUCKET_NAME")
        or os.getenv("R2_BUCKET_NAME")
    )

def _r2_public_base():
    """
    Base pública para montar URL acessível no R2.
    Prioriza variável .env R2_PUBLIC_BASE_URL (ex: https://pub-xxxxxx.r2.dev)
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
    """Extrai o key do objeto no bucket a partir da URL pública salva no banco."""
    if not public_url:
        return None
    try:
        parsed = urlparse(public_url)
        key = parsed.path.lstrip("/")
        return key
    except Exception:
        return None
