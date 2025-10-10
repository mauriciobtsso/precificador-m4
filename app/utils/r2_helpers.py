# ========================================
# app/utils/r2_helpers.py
# ========================================
"""
Funções auxiliares específicas para Cloudflare R2.
Agora este módulo é apenas um wrapper em torno do app/utils/storage.py
para manter compatibilidade com partes do sistema que já chamam gerar_link_r2().
"""

from app.utils.storage import get_s3, get_bucket
import logging


def gerar_link_r2(caminho_arquivo: str, expiracao: int = 3600) -> str:
    """
    Gera um link pré-assinado válido por `expiracao` segundos.
    Usa as mesmas credenciais e conexões configuradas em storage.py.
    """
    if not caminho_arquivo:
        raise ValueError("Caminho do arquivo não informado para gerar link R2.")

    try:
        s3 = get_s3()
        bucket = get_bucket()

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": caminho_arquivo},
            ExpiresIn=expiracao,
        )
        return url

    except Exception as e:
        logging.error(f"[R2] Erro ao gerar link para {caminho_arquivo}: {e}")
        raise
