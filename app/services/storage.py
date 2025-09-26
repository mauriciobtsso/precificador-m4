import boto3
from flask import current_app
from botocore.exceptions import ClientError
import logging
import uuid

def get_s3_client():
    """Cria cliente S3 para R2 Cloudflare"""
    return boto3.client(
        "s3",
        endpoint_url=current_app.config["R2_ENDPOINT_URL"],
        aws_access_key_id=current_app.config["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["R2_SECRET_ACCESS_KEY"],
        region_name="auto",  # R2 ignora região, mas boto3 pede algo
    )

def upload_file(file, filename=None):
    """Faz upload de um arquivo para o bucket"""
    s3 = get_s3_client()
    bucket_name = current_app.config["R2_BUCKET_NAME"]

    # Gera nome único se não passar
    if not filename:
        filename = f"{uuid.uuid4().hex}_{file.filename}"

    try:
        s3.upload_fileobj(
            file,
            bucket_name,
            filename,
            ExtraArgs={"ACL": "private"}  # documentos são privados
        )
        return filename
    except ClientError as e:
        logging.error(e)
        return None

def generate_presigned_url(filename, expires_in=3600):
    """Gera URL temporária para acessar o arquivo"""
    s3 = get_s3_client()
    bucket_name = current_app.config["R2_BUCKET_NAME"]

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": filename},
            ExpiresIn=expires_in
        )
        return url
    except ClientError as e:
        logging.error(e)
        return None

def delete_file(filename):
    """Remove arquivo do bucket"""
    s3 = get_s3_client()
    bucket_name = current_app.config["R2_BUCKET_NAME"]

    try:
        s3.delete_object(Bucket=bucket_name, Key=filename)
        return True
    except ClientError as e:
        logging.error(e)
        return False
