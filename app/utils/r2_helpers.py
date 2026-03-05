from app.utils.storage import get_s3, get_bucket, upload_file
from werkzeug.utils import secure_filename
import logging
import uuid
import os
import boto3
from flask import current_app
from urllib.parse import urlparse

# Configurações Táticas de Arsenal
BUCKET_PRIVADO = "m4-clientes-docs"
BUCKET_PUBLICO = "m4-loja-publico"
CDN_URL = "https://cdn.m4tatica.com.br"

def gerar_link_r2(caminho_arquivo: str, expiracao: int = 3600) -> str:
    """
    Gera o link para o arquivo. 
    SE FOR PÚBLICO (loja/ ou produtos/): Retorna link direto via CDN (Cloudflare Cache).
    SE FOR PRIVADO (documentos): Gera link assinado pelo R2.
    """
    if not caminho_arquivo:
        return ""

    try:
        # Limpeza de URL caso venha o link completo do banco
        if caminho_arquivo.startswith('http'):
            parsed_url = urlparse(caminho_arquivo)
            caminho_arquivo = parsed_url.path.lstrip('/')
            
            # Remove prefixo do bucket antigo se existir no path
            if caminho_arquivo.startswith(BUCKET_PRIVADO + '/'):
                caminho_arquivo = caminho_arquivo[len(BUCKET_PRIVADO) + 1:]

        # 🎯 REGRA DE OURO: Roteamento para o CDN (Performance Máxima)
        # Identifica se o arquivo já foi migrado para o bucket público
        pastas_publicas = ('loja/', 'produtos/')
        if caminho_arquivo.startswith(pastas_publicas):
            return f"{CDN_URL}/{caminho_arquivo}"

        # 🔒 SEGURANÇA: Links assinados para o que restou no bucket privado
        s3 = get_s3()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_PRIVADO, "Key": caminho_arquivo},
            ExpiresIn=expiracao,
        )
        return url

    except Exception as e:
        logging.error(f"[R2] Erro ao gerar link para {caminho_arquivo}: {e}")
        return ""

def upload_file_to_r2(file_storage, folder="uploads") -> str:
    """
    Faz upload selecionando o bucket correto: 
    loja ou produtos -> m4-loja-publico
    outros -> m4-clientes-docs
    """
    if not file_storage:
        return None

    try:
        filename = secure_filename(file_storage.filename)
        if not filename:
            filename = f"file_{uuid.uuid4().hex[:8]}"

        if folder.endswith("/"):
            folder = folder[:-1]
            
        caminho_destino = f"{folder}/{filename}"

        # Seleção automática de Bucket
        bucket_destino = BUCKET_PUBLICO if folder.startswith(('loja', 'produtos')) else BUCKET_PRIVADO

        s3 = get_s3()
        s3.upload_fileobj(
            file_storage,
            bucket_destino,
            caminho_destino,
            ExtraArgs={'ContentType': file_storage.content_type}
        )
        
        return caminho_destino

    except Exception as e:
        logging.error(f"[R2] Erro no upload_file_to_r2: {e}")
        return None

def upload_fileobj_r2(file_obj, folder="uploads"):
    """Wrapper para manter compatibilidade com o módulo de Compras"""
    return upload_file_to_r2(file_obj, folder)