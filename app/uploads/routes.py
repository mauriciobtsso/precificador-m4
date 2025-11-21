# ====================================================================
# UPLOADS E OCR (VERSÃO FINAL REVISADA POR MANUS)
# ====================================================================

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
from app.utils.datetime import now_local
import os
import tempfile

from app.utils.storage import get_s3, get_bucket
from app.services.ocr_pipeline import processar_documento
from app.uploads.parsers import (
    parse_craf,
    parse_cr,
    parse_cnh,
    parse_rg,
    parse_documento_ocr
)
from app.utils.datetime import now_local
uploads_bp = Blueprint("uploads", __name__)

# ==========================
# Funções auxiliares
# ==========================

def _save_temp_file(file_storage, prefix="ocr"):
    """Salva arquivo temporário e retorna caminho."""
    nome_seguro = secure_filename(file_storage.filename)
    fd, tmp_path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=f"_{nome_seguro}")
    os.close(fd)
    file_storage.seek(0)
    with open(tmp_path, "wb") as f:
        f.write(file_storage.read())
    file_storage.seek(0)
    return tmp_path


def _upload_to_r2(file_storage, cliente_id, subpasta):
    """Envia arquivo para o bucket R2 e retorna o caminho da chave."""
    s3 = get_s3()
    bucket = get_bucket()
    nome_seguro = secure_filename(file_storage.filename)
    timestamp = now_local().strftime("%Y%m%d_%H%M%S")
    key = f"clientes/{cliente_id}/{subpasta}/{timestamp}_{nome_seguro}"
    file_storage.seek(0)
    s3.upload_fileobj(file_storage, bucket, key)
    return key


# ==========================
# CRAF (ARMAS)
# ==========================
@uploads_bp.route("/<int:cliente_id>/craf", methods=["POST"])
def upload_craf(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    try:
        file_bytes = file.read()
        file.seek(0)

        caminho_r2 = _upload_to_r2(file, cliente_id, "armas")
        resultado = processar_documento(file_bytes, file.filename)
        dados_raw = resultado.get("resultado", {}) or {}
        
        current_app.logger.info(f"[DEBUG OCR CRAF] Resultado OCR bruto: {dados_raw}")

        # ✅ Mapeamento para um dicionário plano, incluindo todos os campos necessários para o JS
        dados_mapeados = {
            "tipo": dados_raw.get("tipo") or dados_raw.get("tipo_arma") or "",
            "funcionamento": dados_raw.get("funcionamento") or "",
            "marca": dados_raw.get("marca") or "",
            "modelo": dados_raw.get("modelo") or "",
            "calibre": dados_raw.get("calibre") or "",
            "numero_serie": dados_raw.get("numero_serie") or "",
            "numero_sigma": dados_raw.get("numero_sigma") or "",
            "numero_documento": dados_raw.get("numero_documento") or "", # Essencial para a lógica no JS
            "emissor_craf": dados_raw.get("emissor") or "",
            "categoria_adquirente": dados_raw.get("categoria_adquirente") or "",
            "data_validade_craf": dados_raw.get("data_validade") or "",
            "validade_indeterminada": dados_raw.get("validade_indeterminada", False),
            "caminho_craf": caminho_r2,
            "nome_original": secure_filename(file.filename),
        }

        # Log do dicionário exato que será enviado como JSON
        current_app.logger.info(f"[DEBUG FLASK RESPONSE] Enviando JSON: {dados_mapeados}")

        # ✅ Retornando um JSON plano, sem aninhamento
        return jsonify(dados_mapeados)

    except Exception as e:
        current_app.logger.exception(f"[UPLOAD CRAF] Erro: {e}")
        return jsonify({"error": f"Erro no upload do CRAF: {e}"}), 500

# ==========================
# CR
# ==========================

@uploads_bp.route("/<int:cliente_id>/cr", methods=["POST"])
def upload_cr(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    try:
        caminho_r2 = _upload_to_r2(file, cliente_id, "documentos")
        file_bytes = file.read()

        resultado = processar_documento(file_bytes, file.filename)
        dados = resultado.get("resultado", {})

        if not dados.get("categoria") or dados.get("categoria") == "NÃO RECONHECIDO":
            texto_bruto = "\n".join(resultado.get("resultado", {}).get("raw_text", []))
            dados = parse_cr(texto_bruto)

        dados["caminho"] = caminho_r2
        dados["nome_original"] = secure_filename(file.filename)
        return jsonify(dados)

    except Exception as e:
        current_app.logger.exception(f"[UPLOAD CR] Erro: {e}")
        return jsonify({"error": f"Erro no upload do CR: {e}"}), 500


# ==========================
# CNH
# ==========================

@uploads_bp.route("/<int:cliente_id>/cnh", methods=["POST"])
def upload_cnh(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    try:
        caminho_r2 = _upload_to_r2(file, cliente_id, "documentos")
        file_bytes = file.read()

        resultado = processar_documento(file_bytes, file.filename)
        dados = resultado.get("resultado", {})

        if not dados.get("categoria") or dados.get("categoria") == "NÃO RECONHECIDO":
            texto_bruto = "\n".join(resultado.get("resultado", {}).get("raw_text", []))
            dados = parse_cnh(texto_bruto)

        dados["caminho"] = caminho_r2
        dados["nome_original"] = secure_filename(file.filename)
        return jsonify(dados)

    except Exception as e:
        current_app.logger.exception(f"[UPLOAD CNH] Erro: {e}")
        return jsonify({"error": f"Erro no upload da CNH: {e}"}), 500


# ==========================
# RG
# ==========================

@uploads_bp.route("/<int:cliente_id>/rg", methods=["POST"])
def upload_rg(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    try:
        caminho_r2 = _upload_to_r2(file, cliente_id, "documentos")
        file_bytes = file.read()

        resultado = processar_documento(file_bytes, file.filename)
        dados = resultado.get("resultado", {})

        if not dados.get("categoria") or dados.get("categoria") == "NÃO RECONHECIDO":
            texto_bruto = "\n".join(resultado.get("resultado", {}).get("raw_text", []))
            dados = parse_rg(texto_bruto)

        dados["caminho"] = caminho_r2
        dados["nome_original"] = secure_filename(file.filename)
        return jsonify(dados)

    except Exception as e:
        current_app.logger.exception(f"[UPLOAD RG] Erro: {e}")
        return jsonify({"error": f"Erro no upload do RG: {e}"}), 500


# ===============================
# UPLOAD + OCR (PIPELINE COMPLETO)
# ===============================
@uploads_bp.route("/<int:cliente_id>/documento", methods=["POST"])
def upload_documento(cliente_id):
    """
    Recebe um arquivo, salva temporariamente, processa via OCR (local + IA Groq),
    envia para o Cloudflare R2 e retorna os metadados extraídos em formato JSON.
    """
    import traceback
    from app.services import ocr_pipeline

    file = request.files.get("arquivo") or request.files.get("file")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    try:
        filename = secure_filename(file.filename)
        cliente_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], f"cliente_{cliente_id}")
        os.makedirs(cliente_dir, exist_ok=True)

        caminho_arquivo = os.path.join(cliente_dir, filename)
        file.save(caminho_arquivo)

        current_app.logger.info(f"[UPLOAD OCR] Arquivo salvo em: {caminho_arquivo}")

        try:
            s3 = get_s3()
            bucket = get_bucket()
            key_r2 = f"clientes/{cliente_id}/documentos/{filename}"
            file.seek(0)
            s3.upload_fileobj(file, bucket, key_r2)
            current_app.logger.info(f"[UPLOAD OCR] Arquivo enviado ao R2: {key_r2}")
        except Exception as e:
            current_app.logger.warning(f"[UPLOAD OCR] Falha ao enviar ao R2: {e}")
            key_r2 = None

        with open(caminho_arquivo, "rb") as f:
            file_bytes = f.read()

        resultado = ocr_pipeline.processar_documento(file_bytes, filename)
        if not resultado:
            raise RuntimeError("Nenhum resultado retornado pelo pipeline OCR")

        current_app.logger.info(f"[UPLOAD OCR] Resultado OCR: {resultado}")

        resposta = {
            "dados": resultado,
            "ocr_engine": resultado.get("ocr_engine", "local"),
            "ia_engine": resultado.get("engine", "llama-3.1-8b-instant"),
            "caminho_arquivo": key_r2 or caminho_arquivo,
            "nome_original": filename,
        }

        current_app.logger.info(f"[UPLOAD OCR] Retornando JSON: {resposta}")
        return jsonify(resposta)

    except Exception as e:
        current_app.logger.error("[UPLOAD OCR] Falha no pipeline OCR:", exc_info=True)
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500