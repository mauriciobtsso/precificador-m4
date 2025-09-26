import os
import re
import mimetypes
from io import BytesIO
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask import Blueprint
from flask import current_app
from app.extensions import db
from app.models import Cliente, Arma, Documento
import boto3
from botocore.client import Config
from PIL import Image
import pytesseract
import pdfplumber

clientes_bp = Blueprint("clientes", __name__, template_folder="templates")

# Forçar caminho do executável Tesseract no Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ======================
# Config R2
# ======================
R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
R2_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_KEY,
    aws_secret_access_key=R2_SECRET,
    config=Config(signature_version="s3v4"),
)


def gerar_link_craf(caminho_craf):
    """Gera link temporário (5 min) para acessar o arquivo no R2"""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET, "Key": caminho_craf},
        ExpiresIn=300,
    )


# ======================
# LISTAGEM / CADASTRO
# ======================
@clientes_bp.route("/")
def lista():
    clientes = Cliente.query.all()
    return render_template("clientes/index.html", clientes=clientes)


@clientes_bp.route("/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        cliente = Cliente(
            nome=request.form.get("nome"),
            documento=request.form.get("documento"),
            sexo=request.form.get("sexo"),
            data_nascimento=request.form.get("data_nascimento") or None,
            estado_civil=request.form.get("estado_civil"),
            nome_pai=request.form.get("nome_pai"),
            nome_mae=request.form.get("nome_mae"),
            apelido=request.form.get("apelido"),
            naturalidade=request.form.get("naturalidade"),
            profissao=request.form.get("profissao"),
            escolaridade=request.form.get("escolaridade"),
        )
        db.session.add(cliente)
        db.session.commit()

        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for("clientes.detalhe_cliente", cliente_id=cliente.id))

    return render_template("clientes/novo.html")


# ======================
# DETALHE CLIENTE
# ======================
@clientes_bp.route("/<int:cliente_id>")
def detalhe_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template("clientes/detalhe.html", cliente=cliente)

@clientes_bp.route("/<int:cliente_id>/informacoes", methods=["POST"])
def cliente_informacoes(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    try:
        # Campos principais
        cliente.nome = request.form.get("nome")
        cliente.razao_social = request.form.get("razao_social")
        cliente.sexo = request.form.get("sexo")
        cliente.profissao = request.form.get("profissao")
        cliente.documento = request.form.get("documento")
        cliente.rg = request.form.get("rg")
        cliente.rg_emissor = request.form.get("rg_emissor")
        cliente.email = request.form.get("email")
        cliente.telefone = request.form.get("telefone")
        cliente.celular = request.form.get("celular")
        cliente.endereco = request.form.get("endereco")
        cliente.numero = request.form.get("numero")
        cliente.complemento = request.form.get("complemento")
        cliente.bairro = request.form.get("bairro")
        cliente.cidade = request.form.get("cidade")
        cliente.estado = request.form.get("estado")
        cliente.cep = request.form.get("cep")

        # Flags (checkboxes)
        cliente.cac = "cac" in request.form
        cliente.filiado = "filiado" in request.form
        cliente.policial = "policial" in request.form
        cliente.bombeiro = "bombeiro" in request.form
        cliente.militar = "militar" in request.form
        cliente.iat = "iat" in request.form
        cliente.psicologo = "psicologo" in request.form

        db.session.commit()
        flash("Informações do cliente atualizadas com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash("Erro ao atualizar informações do cliente.", "danger")
        current_app.logger.error(f"[cliente_informacoes] Erro: {e}")

    return redirect(url_for("clientes.detalhe_cliente", cliente_id=cliente.id))

# ======================
# DOCUMENTOS
# ======================
@clientes_bp.route("/<int:cliente_id>/documentos")
def cliente_documentos(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template("clientes/abas/documentos.html", cliente=cliente)


@clientes_bp.route("/<int:cliente_id>/documentos/upload", methods=["POST"])
def upload_documento(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    file = request.files.get("arquivo")
    tipo = request.form.get("tipo")

    if not file or not tipo:
        flash("Arquivo e tipo são obrigatórios", "danger")
        return redirect(url_for("clientes.cliente_documentos", cliente_id=cliente.id))

    filename = f"clientes/{cliente.id}/documentos/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    s3.upload_fileobj(file, R2_BUCKET, filename)

    url_arquivo = filename
    mime_type = mimetypes.guess_type(file.filename)[0]

    doc = Documento(
        cliente_id=cliente.id,
        tipo=tipo,
        nome_original=file.filename,
        caminho_arquivo=url_arquivo,
        mime_type=mime_type,
    )
    db.session.add(doc)
    db.session.commit()

    flash("Documento enviado com sucesso!", "success")
    return redirect(url_for("clientes.cliente_documentos", cliente_id=cliente.id))


@clientes_bp.route("/<int:cliente_id>/documentos/<int:doc_id>/delete", methods=["POST"])
def deletar_documento(cliente_id, doc_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    doc = Documento.query.filter_by(id=doc_id, cliente_id=cliente.id).first_or_404()

    if doc.caminho_arquivo:
        try:
            s3.delete_object(Bucket=R2_BUCKET, Key=doc.caminho_arquivo)
        except Exception as e:
            flash(f"Erro ao excluir no R2: {e}", "warning")

    db.session.delete(doc)
    db.session.commit()

    flash("Documento excluído com sucesso!", "success")
    return redirect(url_for("clientes.cliente_documentos", cliente_id=cliente.id))


# ======================
# ARMAS
# ======================
@clientes_bp.route("/<int:cliente_id>/armas", methods=["GET", "POST"])
def cliente_armas(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template("clientes/abas/armas.html", cliente=cliente)


@clientes_bp.route("/<int:cliente_id>/armas/upload", methods=["POST"])
def upload_craf(cliente_id):
    file = request.files.get("file") or request.files.get("arquivo")
    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    filename = f"clientes/{cliente_id}/armas/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = file.read()

    # Upload para R2 (privado)
    s3.upload_fileobj(BytesIO(file_bytes), R2_BUCKET, filename)

    # OCR / PDF
    texto = ""
    if file.filename.lower().endswith(".pdf"):
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            texto = "\n".join(page.extract_text() or "" for page in pdf.pages)
    else:
        img = Image.open(BytesIO(file_bytes))
        texto = pytesseract.image_to_string(img, lang="por")

    print("\n========== TEXTO EXTRAÍDO DO CRAF ==========")
    print(texto)
    print("============================================\n")

    # Regex
    marca = re.search(r"MARCA[:\s]+([A-Z0-9\- ]+)", texto, re.I)
    modelo = re.search(r"MODELO[:\s]+([A-Z0-9\- ]+)", texto, re.I)
    calibre = re.search(r"CALIBRE[:\s]+([A-Z0-9\/\. ]+)", texto, re.I)
    numero_serie = re.search(r"(N[ºo]\s*[:\-]?\s*([A-Z0-9\-]+))", texto, re.I)
    validade = re.search(r"VALIDADE[:\s]+(\d{2}/\d{2}/\d{4})", texto, re.I)

    dados_extraidos = {
        "marca": marca.group(1).strip() if marca else "",
        "modelo": modelo.group(1).strip() if modelo else "",
        "calibre": calibre.group(1).strip() if calibre else "",
        "numero_serie": numero_serie.group(2).strip() if numero_serie else "",
        "data_validade_craf": validade.group(1) if validade else "",
        "caminho_craf": filename,
    }

    return jsonify(dados_extraidos)


@clientes_bp.route("/<int:cliente_id>/armas/salvar", methods=["POST"])
def salvar_craf(cliente_id):
    num_serie = request.form.get("numero_serie")

    if num_serie and Arma.query.filter_by(numero_serie=num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.cliente_armas", cliente_id=cliente_id))

    arma = Arma(
        cliente_id=cliente_id,
        marca=request.form.get("marca"),
        modelo=request.form.get("modelo"),
        calibre=request.form.get("calibre"),
        numero_serie=num_serie,
        data_validade_craf=request.form.get("data_validade_craf"),
        caminho_craf=request.form.get("caminho_craf"),
    )
    db.session.add(arma)
    db.session.commit()

    flash("Arma cadastrada com sucesso!", "success")
    return redirect(url_for("clientes.cliente_armas", cliente_id=cliente_id))


@clientes_bp.route("/armas/<int:arma_id>/abrir")
def abrir_craf(arma_id):
    arma = Arma.query.get_or_404(arma_id)
    url = gerar_link_craf(arma.caminho_craf)
    return redirect(url)


@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/delete", methods=["POST"])
def deletar_arma(cliente_id, arma_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    arma = Arma.query.filter_by(id=arma_id, cliente_id=cliente.id).first_or_404()

    db.session.delete(arma)
    db.session.commit()

    flash("Arma excluída com sucesso!", "success")
    return redirect(url_for("clientes.cliente_armas", cliente_id=cliente.id))
