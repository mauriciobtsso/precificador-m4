import boto3
from flask import current_app
from botocore.client import Config  # 👈 necessário para forçar SigV4


def get_s3():
    """Cria client S3 apontando para o R2 (forçando assinatura SigV4)."""
    return boto3.client(
        "s3",
        endpoint_url=current_app.config["R2_ENDPOINT"],
        aws_access_key_id=current_app.config["R2_ACCESS_KEY"],
        aws_secret_access_key=current_app.config["R2_SECRET_KEY"],
        config=Config(signature_version="s3v4")  # 👈 obrigatório no R2
    )


def get_bucket():
    """Retorna o nome do bucket configurado."""
    return current_app.config["R2_BUCKET"]


def gerar_link_r2(caminho_arquivo: str, expira_em: int = 3600) -> str:
    """
    Gera link presigned (temporário) para abrir arquivo no R2.

    :param caminho_arquivo: caminho salvo no banco (ex: clientes/1/documentos/xpto.pdf)
    :param expira_em: tempo em segundos que o link será válido (default 3600s = 1h)
    :return: URL presigned para download/visualização
    """
    s3 = get_s3()
    bucket = get_bucket()

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": caminho_arquivo},
        ExpiresIn=expira_em
    )
    return url
