# ========================================
# app/utils/r2_helpers.py
# ========================================
"""
Funções auxiliares específicas para Cloudflare R2.
Wrapper para app/utils/storage.py com lógica de pastas e nomes de arquivos.
"""

from app.utils.storage import get_s3, get_bucket, upload_file
from werkzeug.utils import secure_filename
import logging
import uuid
import os

def gerar_link_r2(caminho_arquivo: str, expiracao: int = 3600) -> str:
    """
    Gera um link pré-assinado válido por `expiracao` segundos.
    """
    if not caminho_arquivo:
        return ""

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
        return ""

def upload_file_to_r2(file_storage, folder="uploads") -> str:
    """
    Recebe um objeto FileStorage (Flask), salva no R2 dentro da pasta especificada
    e retorna o caminho (Key) do arquivo salvo.
    
    Ex: folder='vendas/123' -> salva em 'vendas/123/nome-arquivo.pdf'
    """
    if not file_storage:
        return None

    try:
        # Limpa o nome do arquivo
        filename = secure_filename(file_storage.filename)
        
        # Se o nome ficou vazio após limpar, gera um aleatório
        if not filename:
            filename = f"file_{uuid.uuid4().hex[:8]}"

        # Monta o caminho final (Key)
        # Garante que não tenha barras duplicadas
        if folder.endswith("/"):
            folder = folder[:-1]
            
        caminho_destino = f"{folder}/{filename}"

        # Usa a função base do storage.py para fazer o upload real
        upload_file(file_storage, caminho_destino)
        
        return caminho_destino

    except Exception as e:
        logging.error(f"[R2] Erro no upload_file_to_r2: {e}")
        return None