"""
scripts/limpar_thumbs_errados.py
─────────────────────────────────────────────────────────────────────────────
Remove thumbnails (_t80, _t160, _t280) que foram enviados erroneamente
para o bucket privado m4-clientes-docs.

Como rodar:
    # Ver o que seria deletado (sem deletar):
    python scripts/limpar_thumbs_errados.py --dry-run

    # Deletar de verdade:
    python scripts/limpar_thumbs_errados.py
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import argparse
import logging
import boto3
from botocore.config import Config
from dotenv import load_dotenv

# Carrega variáveis do .env (mesmo comportamento do Flask)
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

BUCKET_PRIVADO = "m4-clientes-docs"
SUFIXOS_THUMB = ('_t80.webp', '_t160.webp', '_t280.webp')


def get_r2_client():
    endpoint = os.environ.get('R2_ENDPOINT_URL', '')
    access_key = os.environ.get('R2_ACCESS_KEY_ID', '')
    secret_key = os.environ.get('R2_SECRET_ACCESS_KEY', '')

    if not all([endpoint, access_key, secret_key]):
        logger.error("Variáveis R2_ENDPOINT_URL, R2_ACCESS_KEY_ID e R2_SECRET_ACCESS_KEY não configuradas.")
        sys.exit(1)

    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def listar_thumbs_errados(client, prefixo='produtos/'):
    """Lista todos os objetos no bucket privado que são thumbnails gerados."""
    thumbs = []
    paginator = client.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=BUCKET_PRIVADO, Prefix=prefixo):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if any(key.endswith(sufixo) for sufixo in SUFIXOS_THUMB):
                thumbs.append(key)

    return thumbs


def main():
    parser = argparse.ArgumentParser(description='Remove thumbnails errados do bucket privado')
    parser.add_argument('--dry-run', action='store_true', help='Simula sem deletar')
    args = parser.parse_args()

    client = get_r2_client()

    logger.info(f"Buscando thumbnails errados em '{BUCKET_PRIVADO}/produtos/'...")
    thumbs = listar_thumbs_errados(client)

    if not thumbs:
        logger.info("Nenhum thumbnail encontrado para remover. Bucket já está limpo!")
        return

    logger.info(f"{len(thumbs)} thumbnails encontrados:")
    for key in thumbs:
        logger.info(f"  → {key}")

    if args.dry_run:
        logger.info(f"\n[DRY-RUN] {len(thumbs)} arquivos seriam deletados. Nada foi removido.")
        return

    # Deleta em lotes de 1000 (limite da API S3)
    deletados = 0
    erros = 0
    lote_size = 1000

    for i in range(0, len(thumbs), lote_size):
        lote = thumbs[i:i + lote_size]
        objects = [{'Key': key} for key in lote]

        try:
            resp = client.delete_objects(
                Bucket=BUCKET_PRIVADO,
                Delete={'Objects': objects, 'Quiet': False}
            )
            deletados += len(resp.get('Deleted', []))

            for erro in resp.get('Errors', []):
                logger.error(f"  ✗ Erro ao deletar {erro['Key']}: {erro['Message']}")
                erros += 1

        except Exception as e:
            logger.error(f"Erro no lote de deleção: {e}")
            erros += len(lote)

    logger.info(f"""
══ RESULTADO ════════════════════════════════════
  ✓ Deletados : {deletados}
  ✗ Erros     : {erros}
  Bucket      : {BUCKET_PRIVADO}
═════════════════════════════════════════════════
""")


if __name__ == '__main__':
    main()