# ========================================
# M4 TÁTICA — STORAGE HELPERS (R2 / S3)
# ========================================
"""
Utilitários centralizados para upload e leitura de arquivos
usando o Cloudflare R2 (ou qualquer endpoint compatível S3).
Permite reutilizar a conexão e padronizar prefixos de pastas.

Usado por: app/clientes/routes.py, app/uploads/routes.py, etc.
"""

import boto3
import os
from botocore.client import Config


# ========================================
# CONFIGURAÇÕES DE CONEXÃO
# ========================================

def get_s3():
    """
    Retorna o cliente S3 configurado para Cloudflare R2.
    As credenciais e endpoint devem estar definidas no .env:
        R2_ENDPOINT_URL
        R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY
    """
    endpoint_url = os.getenv("R2_ENDPOINT_URL")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not all([endpoint_url, access_key, secret_key]):
        raise RuntimeError("⚠️ Variáveis R2_* não configuradas no ambiente.")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",  # Cloudflare usa região 'auto'
    )
    return s3


def get_bucket() -> str:
    """
    Retorna o nome do bucket padrão (ex: 'm4-clientes-docs').
    Deve estar definido no .env como R2_BUCKET_NAME.
    """
    bucket = os.getenv("R2_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("⚠️ Bucket R2_BUCKET_NAME não definido.")
    return bucket


# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def upload_file(file_obj, caminho_destino: str):
    """
    Faz upload de um arquivo para o bucket R2.
    file_obj pode ser um FileStorage (Flask) ou BytesIO.
    caminho_destino é o caminho/prefixo dentro do bucket.
    """
    s3 = get_s3()
    bucket = get_bucket()
    s3.upload_fileobj(file_obj, bucket, caminho_destino)
    return caminho_destino


def gerar_link_publico(caminho_arquivo: str, expira_segundos: int = 3600) -> str:
    """
    Gera um link pré-assinado (válido por tempo limitado)
    para abrir o arquivo armazenado no R2.
    """
    s3 = get_s3()
    bucket = get_bucket()

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": caminho_arquivo},
        ExpiresIn=expira_segundos,
    )
    return url


def deletar_arquivo(caminho_arquivo: str) -> bool:
    """
    Remove o arquivo do bucket, se existir.
    Retorna True se conseguir excluir (ou se já não existir).
    Retorna False apenas em falhas reais de conexão/autorização.
    """
    if not caminho_arquivo:
        print("[R2] Nenhum caminho fornecido para exclusão.")
        return True  # nada a excluir → tratado como sucesso

    s3 = get_s3()
    bucket = get_bucket()

    try:
        s3.delete_object(Bucket=bucket, Key=caminho_arquivo)
        print(f"[R2] Arquivo excluído (ou já inexistente): {caminho_arquivo}")
        return True

    except s3.exceptions.NoSuchKey:
        # Caso o arquivo já tenha sido removido
        print(f"[R2] Arquivo não encontrado (já excluído): {caminho_arquivo}")
        return True

    except Exception as e:
        print(f"[R2] Erro ao excluir {caminho_arquivo}: {e}")
        return False
