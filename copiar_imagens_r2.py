"""
Copia as pastas loja/ e produtos/ do bucket m4-clientes-docs para m4-loja-publico.
Uso: python copiar_imagens_r2.py
Requisitos: pip install boto3
"""

import boto3
from botocore.config import Config

# ============================================================
# PREENCHA AQUI COM SUAS CREDENCIAIS
# ============================================================
ACCOUNT_ID = "1202e2896f1ad48f3caa5d520ab29ff0"
ACCESS_KEY_ID = "4d0f9d409b1536e4ba758bb19f9ee9d9"
SECRET_ACCESS_KEY = "1d4a08797fd9f495293fb347f7678d12c7fad5411bf9a5ce3a1c312ab751bb18"

BUCKET_ORIGEM = "m4-clientes-docs"
BUCKET_DESTINO = "m4-loja-publico"
PASTAS = ["loja/", "produtos/"]
# ============================================================

endpoint = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


def copiar_pasta(prefixo):
    print(f"\n📁 Copiando {prefixo}...")
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET_ORIGEM, Prefix=prefixo)

    total = 0
    erros = 0

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            try:
                s3.copy_object(
                    CopySource={"Bucket": BUCKET_ORIGEM, "Key": key},
                    Bucket=BUCKET_DESTINO,
                    Key=key,
                )
                print(f"  ✅ {key}")
                total += 1
            except Exception as e:
                print(f"  ❌ ERRO em {key}: {e}")
                erros += 1

    print(f"\n  Total copiados: {total} | Erros: {erros}")
    return total, erros


if __name__ == "__main__":
    print("🚀 Iniciando cópia de imagens R2...")
    print(f"   Origem:  {BUCKET_ORIGEM}")
    print(f"   Destino: {BUCKET_DESTINO}")

    total_geral = 0
    erros_geral = 0

    for pasta in PASTAS:
        t, e = copiar_pasta(pasta)
        total_geral += t
        erros_geral += e

    print(f"\n{'='*50}")
    print(f"✅ Concluído! Total: {total_geral} arquivos | Erros: {erros_geral}")
    print(f"{'='*50}")
    print(f"\n🌐 Acesse as imagens em: https://cdn.m4tatica.com.br/produtos/sua-imagem.webp")