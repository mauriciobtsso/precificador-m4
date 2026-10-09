# ====================================================================
# UPLOADS E OCR (VERSÃO FINAL REVISADA TÁTICA M4)
# ====================================================================

from functools import wraps
from flask import Blueprint, request, jsonify, current_app, session
from flask_login import current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os

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

_ALLOWED_OCR_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png"})
_MAX_OCR_FILE_SIZE = 15 * 1024 * 1024


def _validar_arquivo_ocr(file_storage):
    """Valida o upload antes de enviá-lo ao storage ou ao OCR."""
    if not file_storage or not file_storage.filename:
        return "Nenhum arquivo enviado."

    nome_seguro = secure_filename(file_storage.filename)
    if not nome_seguro or "." not in nome_seguro:
        return "Arquivo sem extensão válida."

    extensao = nome_seguro.rsplit(".", 1)[1].lower()
    if extensao not in _ALLOWED_OCR_EXTENSIONS:
        return "Formato não permitido. Use PDF, JPG ou PNG."

    try:
        stream = file_storage.stream
        stream.seek(0, os.SEEK_END)
        tamanho = stream.tell()
        stream.seek(0)
    except (AttributeError, OSError):
        return "Não foi possível validar o arquivo enviado."

    if tamanho <= 0:
        return "O arquivo enviado está vazio."
    if tamanho > _MAX_OCR_FILE_SIZE:
        return "O arquivo excede o limite de 15 MB."
    return None


def _upload_autorizado(view):
    """Permite OCR apenas ao cliente dono da sessão ou a um usuário administrativo."""
    @wraps(view)
    def wrapped(cliente_id, *args, **kwargs):
        admin_autenticado = bool(getattr(current_user, "is_authenticated", False))
        cliente_autenticado = session.get("loja_cliente_id")
        try:
            cliente_autenticado = int(cliente_autenticado) == int(cliente_id)
        except (TypeError, ValueError):
            cliente_autenticado = False

        if not (admin_autenticado or cliente_autenticado):
            return jsonify({"error": "Sessão não autorizada para este cliente."}), 403
        return view(cliente_id, *args, **kwargs)
    return wrapped


# ==========================
# Funções auxiliares
# ==========================

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
@_upload_autorizado
def upload_craf(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    erro_arquivo = _validar_arquivo_ocr(file)
    if erro_arquivo:
        return jsonify({"error": erro_arquivo}), 400

    try:
        file.seek(0)
        file_bytes = file.read()
        file.seek(0)
        
        caminho_r2 = _upload_to_r2(file, cliente_id, "armas")
        
        resultado = processar_documento(file_bytes, file.filename)
        dados_raw = resultado.get("resultado", {}) or {}
        
        current_app.logger.info("[OCR CRAF] Processamento concluído.")

        # ✅ Mapeamento para um dicionário plano
        dados_mapeados = {
            "tipo": dados_raw.get("tipo") or dados_raw.get("tipo_arma") or "",
            "funcionamento": dados_raw.get("funcionamento") or "",
            "marca": dados_raw.get("marca") or "",
            "modelo": dados_raw.get("modelo") or "",
            "calibre": dados_raw.get("calibre") or "",
            "numero_serie": dados_raw.get("numero_serie") or "",
            "numero_sigma": dados_raw.get("numero_sigma") or "",
            "numero_documento": dados_raw.get("numero_documento") or "",
            "emissor_craf": dados_raw.get("emissor") or "",
            "categoria_adquirente": dados_raw.get("categoria_adquirente") or "",
            "data_validade_craf": dados_raw.get("data_validade") or "",
            "validade_indeterminada": dados_raw.get("validade_indeterminada", False),
            "caminho_craf": caminho_r2,
            "nome_original": secure_filename(file.filename),
        }

        current_app.logger.info("[OCR CRAF] Resposta preparada; conteúdo documental omitido do log.")
        return jsonify(dados_mapeados)

    except Exception as e:
        current_app.logger.exception(f"[UPLOAD CRAF] Erro: {e}")
        return jsonify({"error": f"Erro no upload do CRAF: {e}"}), 500

# ==========================
# CR
# ==========================
@uploads_bp.route("/<int:cliente_id>/cr", methods=["POST"])
@_upload_autorizado
def upload_cr(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    erro_arquivo = _validar_arquivo_ocr(file)
    if erro_arquivo:
        return jsonify({"error": erro_arquivo}), 400

    try:
        file.seek(0)
        file_bytes = file.read()
        file.seek(0)
        
        caminho_r2 = _upload_to_r2(file, cliente_id, "documentos")

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
@_upload_autorizado
def upload_cnh(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    erro_arquivo = _validar_arquivo_ocr(file)
    if erro_arquivo:
        return jsonify({"error": erro_arquivo}), 400

    try:
        file.seek(0)
        file_bytes = file.read()
        file.seek(0)
        
        caminho_r2 = _upload_to_r2(file, cliente_id, "documentos")

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
@_upload_autorizado
def upload_rg(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    erro_arquivo = _validar_arquivo_ocr(file)
    if erro_arquivo:
        return jsonify({"error": erro_arquivo}), 400

    try:
        file.seek(0)
        file_bytes = file.read()
        file.seek(0)
        
        caminho_r2 = _upload_to_r2(file, cliente_id, "documentos")

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
@_upload_autorizado
def upload_documento(cliente_id):
    """
    Refatorado M4: Lê direto da memória (RAM), processa via OCR 
    e envia direto para o R2 sem tocar no disco efêmero do Render.
    """
    from app.services import ocr_pipeline

    file = request.files.get("arquivo") or request.files.get("file")
    erro_arquivo = _validar_arquivo_ocr(file)
    if erro_arquivo:
        return jsonify({"error": erro_arquivo}), 400

    try:
        filename = secure_filename(file.filename)
        
        # 1. Leitura em Memória PRIMEIRO (Evita erro de arquivo fechado pelo Boto3)
        file.seek(0)
        file_bytes = file.read()
        file.seek(0) # Reset para o upload

        # 2. Envio ao R2
        key_r2 = None
        try:
            key_r2 = _upload_to_r2(file, cliente_id, "documentos")
            current_app.logger.info("[UPLOAD OCR] Arquivo enviado ao armazenamento privado.")
        except Exception as e:
            current_app.logger.warning(
                "[UPLOAD OCR] Falha ao enviar ao R2 (%s).", type(e).__name__
            )
            # Se falhar o R2, ainda podemos tentar retornar o OCR se for crítico, 
            # mas aqui manteremos a consistência de erro.
            return jsonify({"error": "Falha na comunicação com o Storage R2."}), 500

        aviso_ocr = (
            "O arquivo foi anexado, mas o OCR não conseguiu extrair dados confiáveis. "
            "Preencha os campos manualmente e confira cada informação no documento original."
        )
        try:
            resultado = ocr_pipeline.processar_documento(file_bytes, filename)
        except Exception as e:
            current_app.logger.warning(
                "[UPLOAD OCR] Pipeline indisponível (%s); arquivo preservado para cadastro manual.",
                type(e).__name__,
            )
            return jsonify({
                "dados": {},
                "ocr_warning": aviso_ocr,
                "ocr_engine": "indisponível",
                "caminho_arquivo": key_r2,
                "nome_original": filename,
            })

        if not resultado:
            resultado = {"erro": "Nenhum resultado retornado pelo pipeline OCR"}

        dados_ocr = resultado.get("resultado") or {}
        observacoes_ocr = str(dados_ocr.get("observacoes") or "").casefold()
        leitura_insuficiente = bool(resultado.get("erro")) or (
            str(dados_ocr.get("categoria") or "").upper() == "OUTRO"
            and "texto ocr muito curto" in observacoes_ocr
        )
        if leitura_insuficiente:
            current_app.logger.info(
                "[UPLOAD OCR] Arquivo anexado; leitura insuficiente e edição manual necessária."
            )
            return jsonify({
                "dados": {},
                "ocr_warning": aviso_ocr,
                "ocr_engine": resultado.get("ocr_engine", "desconhecido"),
                "caminho_arquivo": key_r2,
                "nome_original": filename,
            })

        current_app.logger.info(
            "[UPLOAD OCR] Processamento concluído (OCR=%s; interpretação=%s).",
            resultado.get("ocr_engine", "desconhecido"),
            resultado.get("engine", "desconhecida"),
        )

        resposta = {
            "dados": resultado,
            "ocr_engine": resultado.get("ocr_engine", "local"),
            "ia_engine": resultado.get("engine", "openai/gpt-oss-20b"),
            "caminho_arquivo": key_r2,
            "nome_original": filename,
        }

        current_app.logger.info("[UPLOAD OCR] Resposta preparada; dados extraídos omitidos do log.")
        return jsonify(resposta)

    except Exception as e:
        current_app.logger.warning(
            "[UPLOAD OCR] Falha ao preparar o documento (%s).", type(e).__name__
        )
        return jsonify({
            "error": "Não foi possível preparar o arquivo. Atualize a página e tente novamente."
        }), 500
