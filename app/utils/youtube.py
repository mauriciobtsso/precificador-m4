"""Helpers seguros para links públicos do YouTube."""

import re
from urllib.parse import parse_qs, urlparse

from app.utils.r2_helpers import CDN_URL

_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def youtube_video_id(value: str | None) -> str | None:
    """Extrai um ID de vídeo de URLs watch, short, embed ou youtu.be."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or len(raw) > 2048:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in _YOUTUBE_HOSTS:
        return None

    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
        video_id = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else None

    return video_id if video_id and _YOUTUBE_ID_RE.fullmatch(video_id) else None


def normalizar_youtube_url(value: str | None) -> str | None:
    """Retorna URL canônica do YouTube ou None para link inválido."""
    video_id = youtube_video_id(value)
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else None


def youtube_embed_url(value: str | None) -> str | None:
    """Gera embed sem cookies e sem aceitar URL externa."""
    video_id = youtube_video_id(value)
    return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1" if video_id else None


def normalizar_video_publico(value: str | None) -> str | None:
    """Aceita YouTube ou um arquivo de vídeo já pertencente ao bucket público."""
    youtube_url = normalizar_youtube_url(value)
    if youtube_url:
        return youtube_url
    if not isinstance(value, str):
        return None
    raw = value.strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    path = parsed.path.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    cdn_host = (urlparse(CDN_URL).hostname or "").lower()
    is_storage_host = host == cdn_host or host.endswith(".r2.dev")
    if is_storage_host and "produtos/videos/" in path and parsed.scheme in {"http", "https"}:
        return raw[:512]
    return None
