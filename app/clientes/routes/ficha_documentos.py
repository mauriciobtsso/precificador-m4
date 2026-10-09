"""Geração administrativa de ficha compacta de documentos do cliente."""

from io import BytesIO
from urllib.parse import unquote

from flask import current_app, flash, redirect, request, send_file, url_for
from flask_login import login_required

from app.clientes import clientes_bp
from app.clientes.ficha_compacta import (
    FichaCompactaError,
    MAX_SOURCE_BYTES,
    montar_ficha_compacta,
)
from app.clientes.models import Arma, Cliente, Documento
from app.utils.r2_helpers import _limpar_path_r2
from app.utils.storage import get_bucket, get_s3


def _categoria_documento(documento: Documento) -> str:
    valor = (documento.categoria or documento.tipo or "").strip().upper()
    if "CRAF" in valor:
        return "CRAF"
    if "CNH" in valor:
        return "CNH"
    if valor == "CR" or ("CERTIFICADO DE REGISTRO" in valor and "ARMA" not in valor):
        return "CR"
    return ""


def _documento_selecionado(cliente_id: int, raw_id: str, categoria: str) -> Documento:
    try:
        documento_id = int(raw_id)
    except (TypeError, ValueError):
        raise FichaCompactaError(f"Selecione um documento válido para {categoria}.") from None

    documento = Documento.query.filter_by(id=documento_id, cliente_id=cliente_id).first()
    if not documento or _categoria_documento(documento) != categoria:
        raise FichaCompactaError(f"O documento selecionado não pertence à categoria {categoria} deste cliente.")
    if not documento.caminho_arquivo:
        raise FichaCompactaError(f"O arquivo do documento {categoria} não está anexado.")
    return documento


def _ler_arquivo_r2(caminho: str, cliente_id: int) -> bytes:
    key = unquote(_limpar_path_r2(caminho or "")).lstrip("/")
    prefixo_cliente = f"clientes/{cliente_id}/"
    if not key.startswith(prefixo_cliente) or ".." in key.split("/"):
        raise FichaCompactaError("Um dos arquivos não está no armazenamento privado deste cliente.")

    objeto = get_s3().get_object(Bucket=get_bucket(), Key=key)
    if int(objeto.get("ContentLength") or 0) > MAX_SOURCE_BYTES:
        body = objeto.get("Body")
        if body:
            body.close()
        raise FichaCompactaError("Cada arquivo selecionado deve ter até 15 MB.")

    body = objeto.get("Body")
    if not body:
        raise FichaCompactaError("Não foi possível ler um dos arquivos selecionados.")
    try:
        conteudo = body.read(MAX_SOURCE_BYTES + 1)
    finally:
        body.close()

    if not conteudo or len(conteudo) > MAX_SOURCE_BYTES:
        raise FichaCompactaError("Um arquivo está vazio ou excede o limite de 15 MB.")
    return conteudo


@clientes_bp.route("/<int:cliente_id>/documentos/ficha-compacta", methods=["POST"])
@login_required
def gerar_ficha_compacta(cliente_id: int):
    """Pré-visualiza ou baixa uma composição A4; não altera os arquivos originais."""
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.form.get("confirmar_conferencia") != "1":
        flash("Confira os arquivos originais e confirme a titularidade antes de gerar a ficha.", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="docs"))

    try:
        cnh = _documento_selecionado(cliente_id, request.form.get("cnh_id"), "CNH")
        cr = _documento_selecionado(cliente_id, request.form.get("cr_id"), "CR")

        try:
            arma_id = int(request.form.get("arma_id", ""))
        except (TypeError, ValueError):
            raise FichaCompactaError("Selecione a arma cujo CRAF deve ser incluído.") from None
        arma = Arma.query.filter_by(id=arma_id, cliente_id=cliente_id).first()
        if not arma or not arma.caminho_craf:
            raise FichaCompactaError("A arma selecionada não possui um CRAF anexado.")

        documentos = [
            ("CNH", _ler_arquivo_r2(cnh.caminho_arquivo, cliente_id), cnh.nome_original or "cnh.pdf"),
            ("CR", _ler_arquivo_r2(cr.caminho_arquivo, cliente_id), cr.nome_original or "cr.pdf"),
            ("CRAF", _ler_arquivo_r2(arma.caminho_craf, cliente_id), "craf.pdf"),
        ]
        pdf_bytes = montar_ficha_compacta(documentos)
    except FichaCompactaError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="docs"))
    except Exception:
        # Não registrar nomes de arquivo, conteúdo de OCR, nem dados dos documentos.
        current_app.logger.error("[FICHA_COMPACTA] Falha técnica para o cliente %s.", cliente_id)
        flash("Não foi possível gerar a ficha. Verifique se os arquivos estão acessíveis e tente novamente.", "danger")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="docs"))

    acao = request.form.get("acao", "baixar")
    resposta = send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=acao != "visualizar",
        download_name=f"ficha-documentos-cliente-{cliente_id}.pdf",
        conditional=False,
        etag=False,
        max_age=0,
    )
    resposta.headers["Cache-Control"] = "private, no-store, max-age=0"
    resposta.headers["Pragma"] = "no-cache"
    resposta.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return resposta
