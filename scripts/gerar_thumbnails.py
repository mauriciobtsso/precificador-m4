"""
scripts/gerar_thumbnails.py
─────────────────────────────────────────────────────────────────────────────
Script para gerar thumbnails de TODAS as imagens já existentes no banco.
Roda uma única vez para processar o acervo atual.

Como rodar:
    cd /seu/projeto
    python scripts/gerar_thumbnails.py

    # Apenas logos de marcas:
    python scripts/gerar_thumbnails.py --tipo marcas

    # Apenas fotos de produtos:
    python scripts/gerar_thumbnails.py --tipo produtos

    # Testar sem fazer upload (dry-run):
    python scripts/gerar_thumbnails.py --dry-run

    # Limitar quantidade (para testar):
    python scripts/gerar_thumbnails.py --limite 10

Correções aplicadas (v2):
  - Download autenticado via boto3 (get_object) para buckets privados no R2
  - Limpeza de fragmentos #hash duplicados nas URLs (ex: arquivo.webp#arquivo.webp)
  - URLs cdn.m4tatica.com.br/* traduzidas para r2_key e lidas diretamente do bucket
  - Fallback para HTTP público caso o cliente R2 não esteja disponível
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import argparse
import urllib.request
import urllib.error
import logging
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# Adiciona o root do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ── Helpers de URL ──────────────────────────────────────────────────────────

def limpar_url(url: str) -> str:
    """
    Remove fragmentos #hash duplicados e normaliza a URL.

    Problema observado:
        .../temp/1b3a511f.webp#1b3a511f.webp  →  .../temp/1b3a511f.webp

    Fragmentos nunca são enviados ao servidor, mas causam confusão no log
    e podem indicar que o path real está incorreto.
    """
    if not url:
        return url
    parsed = urlparse(url)
    # Reconstrói sem o fragmento (6ª componente da tupla = fragment)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        '',           # ← fragment removido
    ))


def url_para_r2_key(url: str, cdn_base: str) -> str | None:
    """
    Converte uma URL do CDN para o r2_key correspondente no bucket.

    Exemplos:
        https://cdn.m4tatica.com.br/produtos/fotos/166/aa4.webp
            → produtos/fotos/166/aa4.webp

        https://pub-xxxx.r2.dev/produtos/fotos/166/aa4.webp
            → produtos/fotos/166/aa4.webp

        https://cdn.m4tatica.com.br/m4-clientes-docs/produtos/...
            → produtos/...   (remove o prefixo do bucket se estiver no path)

    Retorna None se não for possível extrair o key.
    """
    if not url:
        return None

    parsed = urlparse(url)
    path = parsed.path.lstrip('/')

    # Remove o prefixo do bucket se aparecer no path
    # (acontece quando a URL é montada como endpoint/bucket/key)
    bucket = os.environ.get('R2_BUCKET_NAME', 'm4-clientes-docs')
    if path.startswith(f"{bucket}/"):
        path = path[len(bucket) + 1:]

    return path if path else None


def _get_r2_client():
    """Cria cliente S3-compatível para o R2. Retorna None se não configurado."""
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
        logger.warning("boto3 não instalado — download autenticado indisponível.")
        return None


# ── Download de imagem ───────────────────────────────────────────────────────

def baixar_imagem_r2(r2_key: str, r2_client) -> bytes | None:
    """
    Baixa uma imagem diretamente do bucket R2 usando o cliente boto3.
    Funciona mesmo com o bucket com acesso público desabilitado.
    """
    bucket = os.environ.get('R2_BUCKET_NAME', 'm4-clientes-docs')
    try:
        response = r2_client.get_object(Bucket=bucket, Key=r2_key)
        data = response['Body'].read()
        logger.debug(f"  ↓ R2 autenticado OK: {r2_key} ({len(data)/1024:.1f} KiB)")
        return data
    except Exception as e:
        logger.warning(f"  ✗ Falha ao baixar do R2 ({r2_key}): {e}")
        return None


def baixar_imagem_http(url: str) -> bytes | None:
    """
    Baixa uma imagem via HTTP público (fallback).
    Retorna None se receber 401/403/404.
    """
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'M4Tatica-ThumbGen/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            logger.debug(f"  HTTP {e.code} (bucket privado) para {url} — use download R2.")
        elif e.code == 404:
            logger.warning(f"  HTTP 404 (path incorreto no banco?) para {url}")
        else:
            logger.warning(f"  HTTP {e.code} para {url}")
    except Exception as e:
        logger.warning(f"  Não foi possível baixar {url}: {e}")
    return None


def baixar_imagem(url: str, r2_client, cdn_base: str) -> bytes | None:
    """
    Estratégia de download em duas etapas:
      1. Tenta baixar diretamente do R2 via boto3 (autenticado) ← preferencial
      2. Fallback: tenta URL pública via HTTP

    Desta forma funciona tanto para buckets privados quanto públicos.
    """
    # Etapa 1: download autenticado via R2
    if r2_client:
        r2_key = url_para_r2_key(url, cdn_base)
        if r2_key:
            data = baixar_imagem_r2(r2_key, r2_client)
            if data:
                return data
            # Se o key extraído for inválido (404 no R2), não tenta HTTP
            # pois o path no banco provavelmente está errado mesmo
        else:
            logger.warning(f"  Não foi possível extrair r2_key de: {url}")

    # Etapa 2: fallback HTTP
    logger.debug(f"  Tentando HTTP público: {url}")
    return baixar_imagem_http(url)


# ── Processamento em lote ────────────────────────────────────────────────────

def processar_lote(items, cdn_base, r2_client, dry_run=False):
    """
    Processa uma lista de (nome, url) gerando thumbnails.

    items:      lista de (nome: str, url: str)
    cdn_base:   base do CDN, ex: https://cdn.m4tatica.com.br
    r2_client:  cliente boto3 autenticado (ou None para usar só HTTP)
    dry_run:    se True, apenas simula sem fazer upload
    """
    from app.utils.thumbnail_utils import generate_thumbnail, upload_thumb_to_r2, _strip_cdn_prefix

    ok = 0
    erro = 0
    pulo = 0

    for nome, url_original in items:
        if not url_original:
            pulo += 1
            continue

        # ── 1. Limpa fragmentos #hash da URL ──────────────────────────────
        url = limpar_url(url_original)
        if url != url_original:
            logger.info(f"  URL corrigida (fragment removido): {url_original!r} → {url!r}")

        # ── 2. Garante URL completa ───────────────────────────────────────
        if not url.startswith('http'):
            url = f"{cdn_base}/{url.lstrip('/')}"

        logger.info(f"  Processando: {nome} → {url}")

        # ── 3. Baixa a imagem (autenticado ou HTTP) ───────────────────────
        image_bytes = baixar_imagem(url, r2_client, cdn_base)
        if not image_bytes:
            logger.warning(f"  ✗ Falha ao obter imagem: {url}")
            erro += 1
            continue

        original_size_kb = len(image_bytes) / 1024
        r2_key = _strip_cdn_prefix(url)

        p = Path(r2_key)
        base_key = str(p.parent / p.stem)

        # ── 4. Determina tamanhos a gerar ─────────────────────────────────
        if 'logos' in r2_key or 'marcas' in r2_key:
            sizes = ['t80']
        else:
            sizes = ['t280', 't160']

        # ── 5. Gera e envia cada thumbnail ────────────────────────────────
        for size_key in sizes:
            try:
                thumb_bytes = generate_thumbnail(image_bytes, size_key)
                thumb_key = f"{base_key}_{size_key}.webp"
                thumb_size_kb = len(thumb_bytes) / 1024
                economia_kb = original_size_kb - thumb_size_kb

                if dry_run:
                    logger.info(
                        f"  [DRY-RUN] {size_key}: {original_size_kb:.0f} KiB → "
                        f"{thumb_size_kb:.0f} KiB (economia: {economia_kb:.0f} KiB)"
                    )
                    ok += 1
                else:
                    success = upload_thumb_to_r2(thumb_bytes, thumb_key)
                    if success:
                        logger.info(
                            f"  ✓ {size_key}: {original_size_kb:.0f} KiB → "
                            f"{thumb_size_kb:.0f} KiB (economia: {economia_kb:.0f} KiB)"
                        )
                        ok += 1
                    else:
                        logger.error(f"  ✗ Falha no upload: {thumb_key}")
                        erro += 1

            except Exception as e:
                logger.error(f"  ✗ Erro ao gerar {size_key}: {e}")
                erro += 1

    return ok, erro, pulo


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Gera thumbnails para imagens M4 Tática')
    parser.add_argument('--tipo', choices=['marcas', 'produtos', 'todos'], default='todos')
    parser.add_argument('--dry-run', action='store_true', help='Simula sem fazer upload')
    parser.add_argument('--limite', type=int, default=0, help='Limita o número de itens')
    args = parser.parse_args()

    # Inicializa o app Flask para ter acesso ao banco
    from app import create_app, db
    app = create_app()

    cdn_base = os.environ.get('CDN_BASE_URL', 'https://cdn.m4tatica.com.br')

    # Inicializa cliente R2 uma única vez (reutilizado em todos os itens)
    r2_client = _get_r2_client()
    if r2_client:
        logger.info("✓ Cliente R2 autenticado (boto3) pronto — download via bucket privado.")
    else:
        logger.warning(
            "⚠ Cliente R2 não disponível — usando apenas HTTP público.\n"
            "  Defina R2_ENDPOINT_URL, R2_ACCESS_KEY_ID e R2_SECRET_ACCESS_KEY para "
            "habilitar download autenticado."
        )

    with app.app_context():
        total_ok = total_erro = total_pulo = 0

        if args.tipo in ('marcas', 'todos'):
            logger.info("\n══ LOGOS DE MARCAS ══════════════════════════════")
            from app.produtos.configs.models import MarcaProduto
            marcas = MarcaProduto.query.filter(MarcaProduto.logo_url.isnot(None)).all()
            if args.limite:
                marcas = marcas[:args.limite]
            logger.info(f"  {len(marcas)} marcas encontradas")

            items = [(m.nome, m.logo_url) for m in marcas]
            ok, erro, pulo = processar_lote(items, cdn_base, r2_client, args.dry_run)
            total_ok += ok; total_erro += erro; total_pulo += pulo

        if args.tipo in ('produtos', 'todos'):
            logger.info("\n══ FOTOS DE PRODUTOS ═══════════════════════════")
            from app.produtos.models import Produto
            produtos = Produto.query.filter(
                Produto.foto_url.isnot(None),
                Produto.visivel_loja == True
            ).all()
            if args.limite:
                produtos = produtos[:args.limite]
            logger.info(f"  {len(produtos)} produtos encontrados")

            items = [(p.nome, p.foto_url) for p in produtos]
            ok, erro, pulo = processar_lote(items, cdn_base, r2_client, args.dry_run)
            total_ok += ok; total_erro += erro; total_pulo += pulo

        logger.info(f"""
══ RESULTADO FINAL ══════════════════════════════
  ✓ Gerados com sucesso : {total_ok}
  ✗ Erros               : {total_erro}
  ○ Pulados (sem URL)   : {total_pulo}
  Modo                  : {'DRY-RUN (nada enviado)' if args.dry_run else 'REAL'}
  Download              : {'R2 autenticado (boto3)' if r2_client else 'HTTP público (fallback)'}
═════════════════════════════════════════════════
""")


if __name__ == '__main__':
    main()