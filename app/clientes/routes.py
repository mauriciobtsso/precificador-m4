import os
import re
import mimetypes
from io import BytesIO
from datetime import datetime
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import over
from sqlalchemy.sql import label
from sqlalchemy.orm import aliased
from sqlalchemy import select
from sqlalchemy.sql import over

from flask import (
    render_template, request, redirect, url_for,
    flash, jsonify, Blueprint, current_app
)

from app import db
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente
from app.extensions import db
from app.utils.db_helpers import get_or_404
from app.utils.storage import gerar_link_r2
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
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()

    # Telefones (pega o primeiro por cliente usando row_number)
    tel_sq = (
        db.session.query(
            ContatoCliente.cliente_id,
            ContatoCliente.valor.label("telefone_principal"),
            func.row_number().over(
                partition_by=ContatoCliente.cliente_id,
                order_by=ContatoCliente.id
            ).label("rn")
        )
        .filter(func.lower(ContatoCliente.tipo).in_(["telefone", "celular", "whatsapp"]))
        .subquery()
    )
    tel_alias = aliased(tel_sq)

    # E-mails (pega o primeiro por cliente usando row_number)
    email_sq = (
        db.session.query(
            ContatoCliente.cliente_id,
            ContatoCliente.valor.label("email_principal"),
            func.row_number().over(
                partition_by=ContatoCliente.cliente_id,
                order_by=ContatoCliente.id
            ).label("rn")
        )
        .filter(func.lower(ContatoCliente.tipo) == "email")
        .subquery()
    )
    email_alias = aliased(email_sq)

    # Query principal: LEFT JOIN com os subqueries filtrados no rn=1
    query = (
        db.session.query(
            Cliente,
            tel_alias.c.telefone_principal,
            email_alias.c.email_principal,
        )
        .outerjoin(tel_alias, (Cliente.id == tel_alias.c.cliente_id) & (tel_alias.c.rn == 1))
        .outerjoin(email_alias, (Cliente.id == email_alias.c.cliente_id) & (email_alias.c.rn == 1))
    )

    if q:
        q_digits = "".join(filter(str.isdigit, q))  # 🔹 mantém só números

        search_filter = or_(
            Cliente.nome.ilike(f"%{q}%"),
            Cliente.documento.ilike(f"%{q}%"),
            tel_alias.c.telefone_principal.ilike(f"%{q}%"),
            email_alias.c.email_principal.ilike(f"%{q}%"),
        )

        if q_digits:
            # 🔹 Busca CPF/CNPJ sem máscara
            search_filter = or_(
                search_filter,
                func.replace(func.replace(func.replace(Cliente.documento, ".", ""), "-", ""), "/", "").ilike(f"%{q_digits}%")
            )

            # 🔹 Busca telefone sem máscara
            search_filter = or_(
                search_filter,
                func.replace(
                    func.replace(
                        func.replace(
                            func.replace(tel_alias.c.telefone_principal, "(", ""), ")", ""
                        ), "-", ""
                    ), " ", ""
                ).ilike(f"%{q_digits}%")
            )

        query = query.filter(search_filter)

    clientes_pagination = query.order_by(Cliente.nome.asc()).paginate(page=page, per_page=20, error_out=False)

    clientes_list = []
    for cliente, telefone, email in clientes_pagination.items:
        cliente.telefone_principal = telefone
        cliente.email_principal = email
        clientes_list.append(cliente)

    return render_template(
        "clientes/index.html",
        clientes=clientes_list,
        pagination=clientes_pagination,
        q=q,
    )

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
    cliente = get_or_404(Cliente, cliente_id)

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
        enderecos=cliente.enderecos,
        contatos=cliente.contatos,
    )

# =========================
# Editar informações
# =========================
@clientes_bp.route("/<int:cliente_id>/informacoes", methods=["POST"])
def cliente_informacoes(cliente_id):
    cliente = get_or_404(Cliente, cliente_id)
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
    cliente = get_or_404(Cliente, cliente_id)
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
    endereco = get_or_404(EnderecoCliente, endereco_id)

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
    endereco = get_or_404(EnderecoCliente, endereco_id)
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
    cliente = get_or_404(Cliente, cliente_id)
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
    contato = get_or_404(ContatoCliente, contato_id)

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
    contato = get_or_404(ContatoCliente, contato_id)
    try:
        db.session.delete(contato)
        db.session.commit()
        flash("Contato excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir contato: {e}", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

# ======================
# DOCUMENTOS (UPLOAD SIMPLES)
# ======================
from io import BytesIO
from datetime import datetime
from app.clientes.models import Documento

@clientes_bp.route("/<int:cliente_id>/documentos/upload", methods=["POST"])
def upload_documento(cliente_id):
    """Upload simples de documento (sem OCR)."""
    file = request.files.get("arquivo")
    tipo = request.form.get("tipo")

    if not file or not tipo:
        flash("Selecione um tipo de documento e um arquivo.", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))

    # Nome do arquivo no storage
    filename = f"clientes/{cliente_id}/documentos/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = file.read()

    # Upload para R2
    from app.uploads.services import get_s3, get_bucket
    s3 = get_s3()
    bucket = get_bucket()
    s3.upload_fileobj(BytesIO(file_bytes), bucket, filename)

    # Salvar metadados no banco
    doc = Documento(
        cliente_id=cliente_id,
        tipo=tipo,
        nome_original=file.filename,
        caminho_arquivo=filename,
        mime_type=file.mimetype,
    )
    db.session.add(doc)
    db.session.commit()

    flash(f"{tipo} enviado com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# ======================
# DOCUMENTOS - ABRIR
# ======================
@clientes_bp.route("/documentos/<int:doc_id>/abrir")
def abrir_documento(doc_id):
    """Gera link temporário e abre documento do cliente no R2."""
    doc = Documento.query.get_or_404(doc_id)
    if not doc.caminho_arquivo:
        flash("Arquivo não encontrado", "danger")
        return redirect(url_for("clientes.detalhe", cliente_id=doc.cliente_id, _anchor="documentos"))

    url = gerar_link_r2(doc.caminho_arquivo)
    return redirect(url)

# ======================
# DOCUMENTOS (DELETE)
# ======================
@clientes_bp.route("/<int:cliente_id>/documentos/<int:doc_id>/deletar", methods=["POST"])
def deletar_documento(cliente_id, doc_id):
    """Remove documento do cliente."""
    doc = Documento.query.get_or_404(doc_id)

    # Remover do banco
    db.session.delete(doc)
    db.session.commit()

    flash("Documento excluído com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))

# ======================
# ARMAS
# ======================
@clientes_bp.route("/<int:cliente_id>/armas", methods=["GET"])
def cliente_armas(cliente_id):
    # redireciona para a aba "armas" dentro do detalhe do cliente
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


# 🚨 Removemos o upload_craf daqui.
# O upload e OCR do CRAF agora são feitos no módulo `uploads/routes.py`
# Endpoint: /uploads/<cliente_id>/craf (retorna JSON para pré-visualização)


@clientes_bp.route("/<int:cliente_id>/armas/salvar", methods=["POST"])
def salvar_craf(cliente_id):
    """Salva arma no banco, após pré-visualização/edit no front."""
    num_serie = request.form.get("numero_serie")

    if num_serie and Arma.query.filter_by(numero_serie=num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    arma = Arma(
        cliente_id=cliente_id,
        marca=request.form.get("marca"),
        modelo=request.form.get("modelo"),
        calibre=request.form.get("calibre"),
        numero_serie=num_serie,
        data_validade_craf=request.form.get("data_validade_craf"),
        caminho_craf=request.form.get("caminho_craf"),  # veio do endpoint de upload
    )
    db.session.add(arma)
    db.session.commit()

    flash("Arma cadastrada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/deletar", methods=["POST"])
def deletar_arma(cliente_id, arma_id):
    """Deleta arma do cliente."""
    arma = Arma.query.get_or_404(arma_id)
    db.session.delete(arma)
    db.session.commit()
    flash("Arma excluída com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


# ======================
# ARMAS - ABRIR
# ======================
@clientes_bp.route("/armas/<int:arma_id>/abrir")
def abrir_craf(arma_id):
    """Abre o PDF/Imagem do CRAF armazenado no R2."""
    arma = Arma.query.get_or_404(arma_id)
    if not arma.caminho_craf:
        flash("Arquivo não encontrado", "danger")
        return redirect(url_for("clientes.detalhe", cliente_id=arma.cliente_id, _anchor="armas"))

    url = gerar_link_r2(arma.caminho_craf)
    return redirect(url)

# ======================
# CNH
# ======================
@clientes_bp.route("/<int:cliente_id>/documentos/cnh/salvar", methods=["POST"])
def salvar_cnh(cliente_id):
    """Salva CNH como Documento (arquivo + validade)."""
    doc = Documento(
        cliente_id=cliente_id,
        tipo="CNH",
        nome_original=request.form.get("nome") or "CNH",
        caminho_arquivo=request.form.get("caminho"),
        mime_type="application/pdf",  # ajuste se quiser tratar imagem também
        validade=request.form.get("validade") or None
    )
    db.session.add(doc)
    db.session.commit()
    flash("CNH salva com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# ======================
# RG
# ======================
@clientes_bp.route("/<int:cliente_id>/documentos/rg/salvar", methods=["POST"])
def salvar_rg(cliente_id):
    """Salva RG como Documento (arquivo + validade opcional)."""
    doc = Documento(
        cliente_id=cliente_id,
        tipo="RG",
        nome_original=request.form.get("nome") or "RG",
        caminho_arquivo=request.form.get("caminho"),
        mime_type="application/pdf",
        validade=request.form.get("validade") or None
    )
    db.session.add(doc)
    db.session.commit()
    flash("RG salvo com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# ======================
# CR
# ======================
@clientes_bp.route("/<int:cliente_id>/documentos/cr/salvar", methods=["POST"])
def salvar_cr(cliente_id):
    """Salva CR como Documento (arquivo + validade)."""
    doc = Documento(
        cliente_id=cliente_id,
        tipo="CR",
        nome_original=request.form.get("numero_cr") or "CR",
        caminho_arquivo=request.form.get("caminho"),
        mime_type="application/pdf",
        validade=request.form.get("validade") or None
    )
    db.session.add(doc)
    db.session.commit()
    flash("CR salva com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))



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
from datetime import datetime
from app import db
from app.clientes.models import Cliente, Processo
from flask import render_template, request, redirect, url_for, flash

# NOVO PROCESSO
@clientes_bp.route("/<int:cliente_id>/processos/novo", methods=["GET", "POST"])
def novo_processo(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        tipo = request.form.get("tipo")
        status = request.form.get("status")
        descricao = request.form.get("descricao")

        if not tipo or not status:
            flash("Preencha todos os campos obrigatórios do processo.", "warning")
            return redirect(url_for("clientes.novo_processo", cliente_id=cliente.id))

        processo = Processo(
            cliente_id=cliente.id,
            tipo=tipo,
            status=status,
            descricao=descricao,
            data=datetime.now()
        )
        db.session.add(processo)
        db.session.commit()
        flash("Processo cadastrado com sucesso!", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

    # GET → renderiza formulário
    return render_template("clientes/novo_processo.html", cliente=cliente, now=datetime.now())


# EDITAR PROCESSO
@clientes_bp.route("/<int:cliente_id>/processos/<int:proc_id>/editar", methods=["GET", "POST"])
def editar_processo(cliente_id, proc_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    processo = Processo.query.get_or_404(proc_id)

    if request.method == "POST":
        processo.tipo = request.form.get("tipo")
        processo.status = request.form.get("status")
        processo.descricao = request.form.get("descricao")
        db.session.commit()
        flash("Processo atualizado com sucesso!", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

    # GET → abre o formulário de edição
    return render_template("clientes/editar_processo.html", cliente=cliente, processo=processo)


# EXCLUIR PROCESSO
@clientes_bp.route("/<int:cliente_id>/processos/<int:proc_id>/excluir", methods=["POST"])
def excluir_processo(cliente_id, proc_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    processo = Processo.query.get_or_404(proc_id)

    db.session.delete(processo)
    db.session.commit()
    flash("Processo excluído com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))