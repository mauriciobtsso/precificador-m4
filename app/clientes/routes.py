import os
import re
import mimetypes
from io import BytesIO
from datetime import datetime

from flask import (
    render_template, request, redirect, url_for,
    flash, jsonify, Blueprint, current_app
)

from app.extensions import db
from app.clientes.models import (
    Cliente, Documento, Arma, Comunicacao, Processo,
    EnderecoCliente, ContatoCliente
)

import boto3
from botocore.client import Config
from PIL import Image
import pytesseract
import pdfplumber


# =========================
# Blueprint
# =========================
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
def index():
    clientes = Cliente.query.all()
    return render_template("clientes/index.html", clientes=clientes)


@clientes_bp.route("/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        try:
            cliente = Cliente(
                documento=request.form.get("documento"),
                nome=request.form.get("nome"),
                apelido=request.form.get("apelido"),
                razao_social=request.form.get("razao_social"),
                sexo=request.form.get("sexo"),
                data_nascimento=request.form.get("data_nascimento"),
                profissao=request.form.get("profissao"),
                estado_civil=request.form.get("estado_civil"),
                escolaridade=request.form.get("escolaridade"),
                nome_pai=request.form.get("nome_pai"),
                nome_mae=request.form.get("nome_mae"),
                cr=request.form.get("cr"),
                cr_emissor=request.form.get("cr_emissor"),
                sigma=request.form.get("sigma"),
                sinarm=request.form.get("sinarm"),
                cac=bool(request.form.get("cac")),
                filiado=bool(request.form.get("filiado")),
                policial=bool(request.form.get("policial")),
                bombeiro=bool(request.form.get("bombeiro")),
                militar=bool(request.form.get("militar")),
                iat=bool(request.form.get("iat")),
                psicologo=bool(request.form.get("psicologo")),
            )
            db.session.add(cliente)
            db.session.commit()
            flash("Cliente cadastrado com sucesso!", "success")
            return redirect(url_for("clientes.index"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar cliente: {str(e)}", "danger")
    return render_template("clientes/novo.html")


# =========================
# Detalhe
# =========================
@clientes_bp.route("/<int:cliente_id>")
def detalhe(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    resumo = {
        "documentos": len(cliente.documentos),
        "armas": len(cliente.armas),
        "comunicacoes": len(cliente.comunicacoes),
        "processos": len(cliente.processos),
        "vendas": len(cliente.vendas),
    }

    # Alertas inteligentes
    alertas = []
    if not cliente.cr or not cliente.cr_emissor:
        alertas.append("CR não informado.")
    if cliente.data_validade_cr and cliente.data_validade_cr < datetime.now().date():
        alertas.append(
            f"CR vencido em {cliente.data_validade_cr.strftime('%d/%m/%Y')}"
        )

    for doc in cliente.documentos:
        if doc.validade and doc.validade < datetime.now().date():
            alertas.append(
                f"Documento '{doc.tipo}' vencido em {doc.validade.strftime('%d/%m/%Y')}"
            )

    for proc in cliente.processos:
        if proc.status and proc.status.lower() not in ["concluído", "finalizado"]:
            alertas.append(f"Processo em andamento: {proc.tipo} ({proc.status})")

    # Mini Timeline
    eventos = []
    if cliente.vendas:
        ultima_venda = max(
            cliente.vendas, key=lambda v: v.data_abertura or datetime.min, default=None
        )
        if ultima_venda:
            eventos.append(
                {
                    "data": ultima_venda.data_abertura,
                    "tipo": "Venda",
                    "descricao": f"Venda #{ultima_venda.id}",
                }
            )

    if cliente.comunicacoes:
        ultima_com = max(cliente.comunicacoes, key=lambda c: c.data)
        eventos.append(
            {
                "data": ultima_com.data,
                "tipo": "Comunicação",
                "descricao": ultima_com.assunto,
            }
        )

    if cliente.documentos:
        ultimo_doc = max(cliente.documentos, key=lambda d: d.data_upload)
        eventos.append(
            {
                "data": ultimo_doc.data_upload,
                "tipo": "Documento",
                "descricao": ultimo_doc.tipo,
            }
        )

    if cliente.processos:
        ultimo_proc = max(cliente.processos, key=lambda p: p.data)
        eventos.append(
            {
                "data": ultimo_proc.data,
                "tipo": "Processo",
                "descricao": ultimo_proc.descricao or ultimo_proc.tipo,
            }
        )

    timeline = sorted(eventos, key=lambda e: e["data"], reverse=True)[:5]

    # 🔥 retorna já com endereços e contatos
    return render_template(
        "clientes/detalhe.html",
        cliente=cliente,
        resumo=resumo,
        alertas=alertas,
        timeline=timeline,
        enderecos=cliente.enderecos.all() if hasattr(cliente.enderecos, "all") else cliente.enderecos,
        contatos=cliente.contatos.all() if hasattr(cliente.contatos, "all") else cliente.contatos,
    )

# =========================
# Editar informações
# =========================
@clientes_bp.route("/<int:cliente_id>/informacoes", methods=["POST"])
def cliente_informacoes(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        cliente.nome = request.form.get("nome")
        cliente.apelido = request.form.get("apelido")
        cliente.razao_social = request.form.get("razao_social")
        cliente.sexo = request.form.get("sexo")
        cliente.data_nascimento = request.form.get("data_nascimento") or None
        cliente.profissao = request.form.get("profissao")
        cliente.estado_civil = request.form.get("estado_civil")
        cliente.escolaridade = request.form.get("escolaridade")
        cliente.nome_pai = request.form.get("nome_pai")
        cliente.nome_mae = request.form.get("nome_mae")
        cliente.documento = request.form.get("documento")
        cliente.rg = request.form.get("rg")
        cliente.rg_emissor = request.form.get("rg_emissor")
        cliente.cnh = request.form.get("cnh")
        cliente.cr = request.form.get("cr")
        cliente.cr_emissor = request.form.get("cr_emissor")
        cliente.sigma = request.form.get("sigma")
        cliente.sinarm = request.form.get("sinarm")

        # Flags
        cliente.cac = "cac" in request.form
        cliente.filiado = "filiado" in request.form
        cliente.policial = "policial" in request.form
        cliente.bombeiro = "bombeiro" in request.form
        cliente.militar = "militar" in request.form
        cliente.iat = "iat" in request.form
        cliente.psicologo = "psicologo" in request.form

        db.session.commit()
        flash("Informações atualizadas com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar cliente: {str(e)}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


# ======================
# ENDEREÇOS
# ======================
@clientes_bp.route("/<int:cliente_id>/enderecos/adicionar", methods=["POST"])
def adicionar_endereco(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        endereco = EnderecoCliente(
            cliente_id=cliente.id,
            logradouro=request.form.get("logradouro"),
            numero=request.form.get("numero"),
            complemento=request.form.get("complemento"),
            bairro=request.form.get("bairro"),
            cidade=request.form.get("cidade"),
            estado=request.form.get("estado"),
            cep=request.form.get("cep"),
            tipo=request.form.get("tipo"),
        )
        db.session.add(endereco)
        db.session.commit()
        flash("Endereço adicionado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao adicionar endereço: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


@clientes_bp.route("/<int:cliente_id>/enderecos/<int:endereco_id>/editar", methods=["GET", "POST"])
def editar_endereco(cliente_id, endereco_id):
    endereco = EnderecoCliente.query.get_or_404(endereco_id)

    if request.method == "POST":
        try:
            endereco.logradouro = request.form.get("logradouro")
            endereco.numero = request.form.get("numero")
            endereco.complemento = request.form.get("complemento")
            endereco.bairro = request.form.get("bairro")
            endereco.cidade = request.form.get("cidade")
            endereco.estado = request.form.get("estado")
            endereco.cep = request.form.get("cep")
            endereco.tipo = request.form.get("tipo")
            db.session.commit()
            flash("Endereço atualizado com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar endereço: {e}", "danger")

    return render_template("clientes/editar_endereco.html", cliente_id=cliente_id, endereco=endereco)


@clientes_bp.route("/<int:cliente_id>/enderecos/<int:endereco_id>/delete", methods=["POST"])
def deletar_endereco(cliente_id, endereco_id):
    endereco = EnderecoCliente.query.get_or_404(endereco_id)
    try:
        db.session.delete(endereco)
        db.session.commit()
        flash("Endereço excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir endereço: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

# ======================
# CONTATOS
# ======================
@clientes_bp.route("/<int:cliente_id>/contatos/adicionar", methods=["POST"])
def adicionar_contato(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        contato = ContatoCliente(
            cliente_id=cliente.id,
            tipo=request.form.get("tipo"),
            valor=request.form.get("valor")
        )
        db.session.add(contato)
        db.session.commit()
        flash("Contato adicionado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao adicionar contato: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


@clientes_bp.route("/<int:cliente_id>/contatos/<int:contato_id>/editar", methods=["GET", "POST"])
def editar_contato(cliente_id, contato_id):
    contato = ContatoCliente.query.get_or_404(contato_id)

    if request.method == "POST":
        try:
            contato.tipo = request.form.get("tipo")
            contato.valor = request.form.get("valor")
            db.session.commit()
            flash("Contato atualizado com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar contato: {e}", "danger")

    return render_template("clientes/editar_contato.html", cliente_id=cliente_id, contato=contato)


@clientes_bp.route("/<int:cliente_id>/contatos/<int:contato_id>/delete", methods=["POST"])
def deletar_contato(cliente_id, contato_id):
    contato = ContatoCliente.query.get_or_404(contato_id)
    try:
        db.session.delete(contato)
        db.session.commit()
        flash("Contato excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir contato: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

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
    if not arma.caminho_craf:
        flash("Arquivo não encontrado", "danger")
        return redirect(url_for("clientes.cliente_armas", cliente_id=arma.cliente_id))

    url = gerar_link_craf(arma.caminho_craf)
    return redirect(url)


# ======================
# COMUNICAÇÕES
# ======================
@clientes_bp.route("/<int:cliente_id>/comunicacoes", methods=["GET", "POST"])
def cliente_comunicacoes(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template("clientes/abas/comunicacoes.html", cliente=cliente)

# =========================
# Alias para adicionar comunicação (retrocompatibilidade)
# =========================
@clientes_bp.route("/<int:cliente_id>/comunicacoes/nova", methods=["POST"])
def nova_comunicacao(cliente_id):
    return cliente_comunicacoes(cliente_id)



# ======================
# PROCESSOS
# ======================
@clientes_bp.route("/<int:cliente_id>/processos", methods=["GET", "POST"])
def cliente_processos(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template("clientes/abas/processos.html", cliente=cliente)

# =========================
# Alias para adicionar processo (retrocompatibilidade)
# =========================
@clientes_bp.route("/<int:cliente_id>/processos/novo", methods=["POST"])
def novo_processo(cliente_id):
    return cliente_processos(cliente_id)
