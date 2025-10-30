import uuid
from flask import request, jsonify, current_app
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from .. import produtos_bp
from app.produtos.models import Produto
from .utils import _r2_bucket, _r2_client, _r2_public_base, _key_from_url, _guess_ext

@produtos_bp.route("/<int:produto_id>/foto", methods=["POST"])
@produtos_bp.route("/foto-temp", methods=["POST"])
@login_required
def upload_foto_produto(produto_id=None):
    """
    Upload da foto do produto para o Cloudflare R2.
    CORREÇÃO: Não persiste foto_url no banco para evitar conflito de sessão.
    Retorna a URL pública para o JS salvar no campo oculto do formulário principal.
    """
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
        bucket = _r2_bucket()
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

        # monta a URL pública
        base_public = _r2_public_base()
        foto_url = (
            f"{base_public.rstrip('/')}/{key}"
            if base_public
            else f"{current_app.config.get('R2_ENDPOINT_URL', '').rstrip('/')}/{bucket}/{key}"
        )

        current_app.logger.info(f"[M4] Upload R2 concluído. URL pública gerada: {foto_url}")
        # Retorna a URL pública para o JS salvar no campo oculto
        if not produto_id:
            # Adiciona a chave do arquivo no final da URL para o JS poder usar para deletar.
            foto_url_com_chave = f"{foto_url}#{key.split('/')[-1]}"
            return jsonify({"success": True, "url": foto_url_com_chave}), 200

        return jsonify({"success": True, "url": foto_url}), 200

    except Exception as e:
        current_app.logger.exception("[M4] Falha no upload da foto para o R2.")
        return jsonify({"success": False, "error": str(e)}), 500


# ======================
# OBTER URL TEMPORÁRIA DA FOTO
# ======================
@produtos_bp.route("/foto-temp/<path:temp_key>", methods=["DELETE"])
@login_required
def remover_foto_temp(temp_key):
    """Remove uma foto temporária do R2."""
    bucket = _r2_bucket()
    if not bucket:
        return jsonify({"success": False, "error": "Bucket R2 não configurado."}), 500

    try:
        client = _r2_client()
        key = f"produtos/fotos/temp/{temp_key}"
        client.delete_object(Bucket=bucket, Key=key)
        current_app.logger.info(f"[M4] Foto temporária removida do R2: {key}")
        return jsonify({"success": True}), 200
    except Exception as e:
        current_app.logger.exception(f"[M4] Falha ao remover foto temporária do R2: {temp_key}")
        return jsonify({"success": False, "error": str(e)}), 500


@produtos_bp.route("/<int:produto_id>/foto-url", methods=["GET"])
@login_required
def obter_url_foto_produto(produto_id):
    """Retorna uma URL temporária (assinada) para visualizar a foto no R2."""
    from botocore.exceptions import ClientError

    produto = Produto.query.get_or_404(produto_id)
    if not produto.foto_url:
        return jsonify({"success": False, "url": None}), 404

    bucket = _r2_bucket()
    key = _key_from_url(produto.foto_url)
    if not bucket or not key:
        return jsonify({"success": False, "url": None}), 404

    try:
        client = _r2_client()
        signed_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=300  # URL válida por 5 minutos
        )
        return jsonify({"success": True, "url": signed_url}), 200
    except ClientError as e:
        current_app.logger.exception("Erro ao gerar URL temporária da foto.")
        return jsonify({"success": False, "url": None, "error": str(e)}), 500


@produtos_bp.route("/<int:produto_id>/foto", methods=["DELETE"])
@login_required
def remover_foto_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    bucket = _r2_bucket()
    if not bucket:
        return jsonify({"success": False, "error": "Bucket R2 não configurado."}), 500

    try:
        client = _r2_client()
        old_key = _key_from_url(produto.foto_url)

        if old_key:
            try:
                client.delete_object(Bucket=bucket, Key=old_key)
            except Exception:
                current_app.logger.warning("Falha ao remover objeto do R2 (seguindo mesmo assim).")

        produto.foto_url = None
        db.session.commit()

        return jsonify({"success": True}), 200

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Erro SQL ao remover foto_url.")
        return jsonify({"success": False, "error": "Erro ao atualizar o produto."}), 500
    except Exception:
        current_app.logger.exception("Falha ao remover foto do R2.")
        return jsonify({"success": False, "error": "Falha ao remover a foto."}), 500
