from flask import request, jsonify
from io import BytesIO
from datetime import datetime
from app.uploads import uploads_bp
from app.uploads.services import extrair_texto, get_s3, get_bucket
from app.uploads.parsers import parse_craf, parse_cr, parse_cnh, parse_rg


# ---------------------
# UPLOAD CRAF
# ---------------------
@uploads_bp.route("/<int:cliente_id>/craf", methods=["POST"])
def upload_craf(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    filename = f"clientes/{cliente_id}/armas/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = file.read()

    # Upload para R2
    s3 = get_s3()
    bucket = get_bucket()
    s3.upload_fileobj(BytesIO(file_bytes), bucket, filename)

    # OCR
    texto = extrair_texto(file_bytes, file.filename)
    dados = parse_craf(texto)
    dados["caminho_craf"] = filename

    return jsonify(dados)


# ---------------------
# UPLOAD CR
# ---------------------
@uploads_bp.route("/<int:cliente_id>/cr", methods=["POST"])
def upload_cr(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    filename = f"clientes/{cliente_id}/documentos/cr_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = file.read()

    s3 = get_s3()
    bucket = get_bucket()
    s3.upload_fileobj(BytesIO(file_bytes), bucket, filename)

    texto = extrair_texto(file_bytes, file.filename)
    dados = parse_cr(texto)
    dados["caminho"] = filename

    return jsonify(dados)


# ---------------------
# UPLOAD CNH
# ---------------------
@uploads_bp.route("/<int:cliente_id>/cnh", methods=["POST"])
def upload_cnh(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    filename = f"clientes/{cliente_id}/documentos/cnh_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = file.read()

    s3 = get_s3()
    bucket = get_bucket()
    s3.upload_fileobj(BytesIO(file_bytes), bucket, filename)

    texto = extrair_texto(file_bytes, file.filename)
    dados = parse_cnh(texto)
    dados["caminho"] = filename

    return jsonify(dados)


# ---------------------
# UPLOAD RG
# ---------------------
@uploads_bp.route("/<int:cliente_id>/rg", methods=["POST"])
def upload_rg(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    filename = f"clientes/{cliente_id}/documentos/rg_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = file.read()

    s3 = get_s3()
    bucket = get_bucket()
    s3.upload_fileobj(BytesIO(file_bytes), bucket, filename)

    texto = extrair_texto(file_bytes, file.filename)
    dados = parse_rg(texto)
    dados["caminho"] = filename

    return jsonify(dados)
