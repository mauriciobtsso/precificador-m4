# ========================================
# app/utils/r2_helpers.py (Completo)
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
from flask import current_app

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
        if folder.endswith("/"):
            folder = folder[:-1]
            
        caminho_destino = f"{folder}/{filename}"

        # Usa a função base do storage.py para fazer o upload real
        upload_file(file_storage, caminho_destino)
        
        return caminho_destino

    except Exception as e:
        logging.error(f"[R2] Erro no upload_file_to_r2: {e}")
        return None

def upload_fileobj_r2(file_obj, folder="uploads"):
    """
    Faz upload de um objeto arquivo (FileStorage ou bytes) para o Cloudflare R2.
    Retorna a URL pública ou caminho relativo (Key) do arquivo.
    (Versão simplificada usada pelo módulo de Compras)
    """
    try:
        # Reutiliza a lógica robusta acima
        key = upload_file_to_r2(file_obj, folder)
        if key:
            # Retorna URL pública se configurada, senão retorna a Key
            if current_app.config.get("R2_PUBLIC_URL"):
                return f"{current_app.config['R2_PUBLIC_URL']}/{key}"
            return key
        return None
    except Exception as e:
        print(f"[R2 Upload Error] {e}")
        return None