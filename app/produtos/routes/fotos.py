# app/produtos/routes/fotos.py
import uuid
from pathlib import Path
from flask import request, jsonify, current_app
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError
from app import db
from .. import produtos_bp
from app.produtos.models import Produto
# IMPORT ATUALIZADO: Usamos _r2_bucket_publico para garantir a sincronia
from .utils import _r2_bucket, _r2_bucket_publico, _r2_client, _r2_public_base, _key_from_url, _guess_ext

VIDEO_MIME_EXT = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
MAX_VIDEO_BYTES = 100 * 1024 * 1024
TOUR360_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_TOUR360_FRAME_BYTES = 15 * 1024 * 1024


def _video_extension(file):
    content_type = (file.mimetype or "").lower().split(";")[0].strip()
    ext = VIDEO_MIME_EXT.get(content_type)
    if not ext:
        suffix = Path(file.filename or "").suffix.lower()
        ext = suffix if suffix in {".mp4", ".webm", ".mov"} else None
        if ext:
            content_type = {value: key for key, value in VIDEO_MIME_EXT.items()}[ext]
    return content_type, ext


@produtos_bp.route('/api/upload_video', methods=['POST'])
@login_required
def api_upload_video():
    """Uploada um vídeo da galeria para o bucket público do R2."""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Arquivo de vídeo não enviado"}), 400
    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "error": "Arquivo de vídeo inválido"}), 400
    if request.content_length and request.content_length > MAX_VIDEO_BYTES + 1024 * 1024:
        return jsonify({"success": False, "error": "O vídeo deve ter no máximo 100 MB."}), 413
    content_type, ext = _video_extension(file)
    if not ext:
        return jsonify({"success": False, "error": "Formato não suportado. Use MP4, WebM ou MOV."}), 415
    produto_id_str = request.form.get('produto_id')
    produto_id = int(produto_id_str) if produto_id_str and produto_id_str.isdigit() else None
    key = f"produtos/videos/{produto_id or 'temp'}/{uuid.uuid4().hex}{ext}"
    try:
        bucket = _r2_bucket_publico()
        client = _r2_client()
        file.seek(0)
        client.upload_fileobj(
            Fileobj=file,
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type or f"video/{ext.lstrip('.')}",
                "CacheControl": "public, max-age=31536000, immutable",
            },
        )
        base_public = _r2_public_base()
        video_url = (
            f"{base_public.rstrip('/')}/{key}"
            if base_public
            else f"{current_app.config.get('R2_ENDPOINT_URL', '').rstrip('/')}/{bucket}/{key}"
        )
        if not produto_id:
            video_url = f"{video_url}#{key.split('/')[-1]}"
        return jsonify({"success": True, "video_url": video_url, "content_type": content_type}), 200
    except Exception as e:
        current_app.logger.exception("[M4] Falha no upload do vídeo para o R2.")
        return jsonify({"success": False, "error": str(e)}), 500


@produtos_bp.route("/video-temp/<path:temp_key>", methods=["DELETE"])
@login_required
def remover_video_temp(temp_key):
    try:
        client = _r2_client()
        client.delete_object(Bucket=_r2_bucket_publico(), Key=f"produtos/videos/temp/{temp_key}")
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@produtos_bp.route('/api/upload_foto', methods=['POST'])
@login_required
def api_upload_foto():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Arquivo 'file' não enviado"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Arquivo inválido"}), 400

    produto_id_str = request.form.get('produto_id')
    produto_id = int(produto_id_str) if produto_id_str and produto_id_str.isdigit() else None
    
    try:
        content_type = file.mimetype or "image/jpeg"
        ext = _guess_ext(content_type)
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        if produto_id:
            key = f"produtos/fotos/{produto_id}/{uuid.uuid4().hex}{ext}"
        else:
            key = f"produtos/fotos/temp/{uuid.uuid4().hex}{ext}"

        # ALVO CORRIGIDO: Sincronizado com os thumbnails e o CDN
        bucket = _r2_bucket_publico()
        client = _r2_client()
        file.seek(0) 
        
        client.upload_fileobj(
            Fileobj=file,
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": "private, max-age=31536000, immutable",
            },
        )

        base_public = _r2_public_base()
        foto_url = (
            f"{base_public.rstrip('/')}/{key}"
            if base_public
            else f"{current_app.config.get('R2_ENDPOINT_URL', '').rstrip('/')}/{bucket}/{key}"
        )

        current_app.logger.info(f"[M4] Upload R2 API concluído no bucket Público. URL: {foto_url}")
        
        if not produto_id:
            foto_url_com_chave = f"{foto_url}#{key.split('/')[-1]}"
            return jsonify({"success": True, "foto_url": foto_url_com_chave}), 200

        return jsonify({"success": True, "foto_url": foto_url}), 200

    except Exception as e:
        current_app.logger.exception("[M4] Falha no upload da foto via API para o R2.")
        return jsonify({"success": False, "error": str(e)}), 500

@produtos_bp.route("/<int:produto_id>/foto", methods=["POST"])
@produtos_bp.route("/foto-temp", methods=["POST"])
@login_required
def upload_foto_produto(produto_id=None):
    produto = None
    if produto_id:
        produto = Produto.query.get_or_404(produto_id)

    if "foto" not in request.files:
        return jsonify({"success": False, "error": "Arquivo não enviado"}), 400

    file = request.files["foto"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Arquivo inválido"}), 400

    try:
        content_type = file.mimetype or "image/jpeg"
        ext = _guess_ext(content_type)
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        if produto_id:
            key = f"produtos/fotos/{produto_id}/{uuid.uuid4().hex}{ext}"
        else:
            key = f"produtos/fotos/temp/{uuid.uuid4().hex}{ext}"
        
        # ALVO CORRIGIDO: Sincronizado com os thumbnails e o CDN
        bucket = _r2_bucket_publico()
        client = _r2_client()
        file.seek(0)

        client.upload_fileobj(
            Fileobj=file,
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": "private, max-age=31536000, immutable",
            },
        )

        base_public = _r2_public_base()
        foto_url = (
            f"{base_public.rstrip('/')}/{key}"
            if base_public
            else f"{current_app.config.get('R2_ENDPOINT_URL', '').rstrip('/')}/{bucket}/{key}"
        )

        if not produto_id:
            foto_url_com_chave = f"{foto_url}#{key.split('/')[-1]}"
            return jsonify({"success": True, "url": foto_url_com_chave}), 200

        return jsonify({"success": True, "url": foto_url}), 200

    except Exception as e:
        current_app.logger.exception("[M4] Falha no upload da foto para o R2.")
        return jsonify({"success": False, "error": str(e)}), 500

@produtos_bp.route("/foto-temp/<path:temp_key>", methods=["DELETE"])
@login_required
def remover_foto_temp(temp_key):
    bucket = _r2_bucket_publico()
    try:
        client = _r2_client()
        key = f"produtos/fotos/temp/{temp_key}" 
        client.delete_object(Bucket=bucket, Key=key)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@produtos_bp.route("/<int:produto_id>/foto-url", methods=["GET"])
@login_required
def obter_url_foto_produto(produto_id):
    from botocore.exceptions import ClientError

    produto = Produto.query.get_or_404(produto_id)
    if not produto.foto_url:
        return jsonify({"success": False, "url": None}), 404

    bucket = _r2_bucket_publico()
    key = _key_from_url(produto.foto_url)
    if not key:
        return jsonify({"success": False, "url": None}), 404

    try:
        client = _r2_client()
        signed_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=300 
        )
        return jsonify({"success": True, "url": signed_url}), 200
    except ClientError as e:
        return jsonify({"success": False, "url": None, "error": str(e)}), 500

@produtos_bp.route("/<int:produto_id>/foto", methods=["DELETE"])
@login_required
def remover_foto_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    bucket = _r2_bucket_publico()
    
    try:
        client = _r2_client()
        old_key = _key_from_url(produto.foto_url)

        if old_key:
            try:
                client.delete_object(Bucket=bucket, Key=old_key)
            except Exception:
                pass

        produto.foto_url = None
        db.session.commit()
        return jsonify({"success": True}), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "Erro ao atualizar o produto."}), 500
    except Exception:
        return jsonify({"success": False, "error": "Falha ao remover a foto."}), 500


@produtos_bp.route('/api/upload_tour360_frame', methods=['POST'])
@login_required
def api_upload_tour360_frame():
    """Uploada um frame de imagem do tour 360 para o R2."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "Frame do tour 360 não enviado"}), 400
    if request.content_length and request.content_length > MAX_TOUR360_FRAME_BYTES + 1024 * 1024:
        return jsonify({"success": False, "error": "Cada frame deve ter no máximo 15 MB."}), 413
    content_type = (file.mimetype or "").lower().split(";")[0].strip()
    ext = TOUR360_MIME_EXT.get(content_type)
    if not ext:
        return jsonify({"success": False, "error": "Use frames JPG, PNG ou WebP."}), 415
    produto_id_str = request.form.get('produto_id')
    produto_id = int(produto_id_str) if produto_id_str and produto_id_str.isdigit() else None
    key = f"produtos/tours360/{produto_id or 'temp'}/{uuid.uuid4().hex}{ext}"
    try:
        bucket = _r2_bucket_publico()
        client = _r2_client()
        file.seek(0)
        client.upload_fileobj(
            Fileobj=file,
            Bucket=bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type, "CacheControl": "public, max-age=31536000, immutable"},
        )
        base_public = _r2_public_base()
        frame_url = (
            f"{base_public.rstrip('/')}/{key}"
            if base_public
            else f"{current_app.config.get('R2_ENDPOINT_URL', '').rstrip('/')}/{bucket}/{key}"
        )
        if not produto_id:
            frame_url = f"{frame_url}#{key.split('/')[-1]}"
        return jsonify({"success": True, "frame_url": frame_url}), 200
    except Exception as e:
        current_app.logger.exception("[M4] Falha no upload do frame 360 para o R2.")
        return jsonify({"success": False, "error": str(e)}), 500


@produtos_bp.route("/tour360-temp/<path:temp_key>", methods=["DELETE"])
@login_required
def remover_tour360_temp(temp_key):
    try:
        _r2_client().delete_object(
            Bucket=_r2_bucket_publico(),
            Key=f"produtos/tours360/temp/{temp_key}",
        )
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
