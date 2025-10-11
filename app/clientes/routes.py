# ======================
# CLIENTES - ROTAS
# ======================

import os
import re
import mimetypes
from io import BytesIO
from datetime import datetime

from sqlalchemy import or_, func, select
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.sql import label, over

from flask import (
    render_template, request, redirect, url_for,
    flash, jsonify, Blueprint, current_app
)

from app import db
from app.utils.db_helpers import get_or_404
from app.utils.r2_helpers import gerar_link_r2

from app.clientes.models import (
    Cliente, Documento, Arma, Comunicacao, Processo,
    EnderecoCliente, ContatoCliente
)

# Certifique-se de que todas as constantes necessárias estão sendo importadas
from app.clientes.constants import (
    TIPOS_ARMA,
    FUNCIONAMENTO_ARMA,
    EMISSORES_CRAF,
    CATEGORIAS_ADQUIRENTE,
    CATEGORIAS_DOCUMENTO,
    EMISSORES_DOCUMENTO,
)

import boto3
from botocore.client import Config
from PIL import Image
import pytesseract
import pdfplumber
from werkzeug.utils import secure_filename

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

def gerar_link_craf(caminho_craf: str):
    """Gera link temporário (5 min) para acessar o arquivo no R2."""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET, "Key": caminho_craf},
        ExpiresIn=300,
    )

# ----------------------
# Helper: Converte string para data
# ----------------------
def parse_date(value):
    """Converte 'YYYY-MM-DD' ou 'DD/MM/YYYY' para date (ou None)."""
    if not value or not str(value).strip():
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None

# ======================
# LISTAR CLIENTES
# ======================
@clientes_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()

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
        q_digits = "".join(filter(str.isdigit, q))

        search_filter = or_(
            Cliente.nome.ilike(f"%{q}%"),
            Cliente.documento.ilike(f"%{q}%"),
            tel_alias.c.telefone_principal.ilike(f"%{q}%"),
            email_alias.c.email_principal.ilike(f"%{q}%"),
        )

        if q_digits:
            search_filter = or_(
                search_filter,
                func.replace(func.replace(func.replace(Cliente.documento, ".", ""), "-", ""), "/", "").ilike(f"%{q_digits}%")
            )
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

# ======================
# NOVO CLIENTE
# ======================
@clientes_bp.route("/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        try:
            documento = request.form.get("documento")

            if documento:
                existente = Cliente.query.filter_by(documento=documento).first()
                if existente:
                    flash("Já existe um cliente cadastrado com este CPF/CNPJ.", "warning")
                    return redirect(url_for("clientes.cliente_detalhe", cliente_id=existente.id))

            cliente = Cliente(
                nome=request.form.get("nome"),
                apelido=request.form.get("apelido"),
                razao_social=request.form.get("razao_social"),
                sexo=request.form.get("sexo"),
                data_nascimento=parse_date(request.form.get("data_nascimento")),
                profissao=request.form.get("profissao"),
                estado_civil=request.form.get("estado_civil"),
                escolaridade=request.form.get("escolaridade"),
                nome_pai=request.form.get("nome_pai"),
                nome_mae=request.form.get("nome_mae"),
                documento=documento,
                cac=bool(request.form.get("cac")),
                filiado=bool(request.form.get("filiado")),
                policial=bool(request.form.get("policial")),
                bombeiro=bool(request.form.get("bombeiro")),
                militar=bool(request.form.get("militar")),
                iat=bool(request.form.get("iat")),
                psicologo=bool(request.form.get("psicologo")),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            db.session.add(cliente)
            db.session.flush()

            cep = request.form.get("cep")
            endereco = request.form.get("endereco")
            numero = request.form.get("numero")
            bairro = request.form.get("bairro")
            cidade = request.form.get("cidade")
            estado = request.form.get("estado")

            if any([cep, endereco, bairro, cidade, estado]):
                end = EnderecoCliente(
                    cliente_id=cliente.id,
                    tipo="residencial",
                    cep=cep,
                    endereco=endereco,
                    numero=numero,
                    complemento=request.form.get("complemento"),
                    bairro=bairro,
                    cidade=cidade,
                    estado=estado,
                )
                db.session.add(end)

            email = request.form.get("email")
            telefone = request.form.get("telefone")
            celular = request.form.get("celular")

            if email:
                db.session.add(ContatoCliente(cliente_id=cliente.id, tipo="email", valor=email))
            if telefone:
                db.session.add(ContatoCliente(cliente_id=cliente.id, tipo="telefone", valor=telefone))
            if celular:
                db.session.add(ContatoCliente(cliente_id=cliente.id, tipo="celular", valor=celular))

            db.session.commit()
            flash("Cliente cadastrado com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

        except Exception as e:
            db.session.rollback()
            print("Erro ao salvar cliente:", e)
            flash(f"Erro ao salvar cliente: {e}", "danger")
            return redirect(url_for("clientes.novo_cliente"))

    return render_template("clientes/novo.html")

# ======================
# DETALHE DO CLIENTE
# ======================
@clientes_bp.route("/<int:cliente_id>")
def detalhe(cliente_id):
    try:
        cliente = (
            Cliente.query
            .options(
                joinedload(Cliente.enderecos),
                joinedload(Cliente.contatos),
                joinedload(Cliente.documentos),
                joinedload(Cliente.armas),
                joinedload(Cliente.comunicacoes),
                joinedload(Cliente.processos)
            )
            .get_or_404(cliente_id)
        )

        resumo = {
            "documentos": len(cliente.documentos or []),
            "armas": len(cliente.armas or []),
            "comunicacoes": len(cliente.comunicacoes or []),
            "processos": len(cliente.processos or []),
        }

        alertas = []
        # Lógica de alertas (exemplo)
        if not cliente.cr:
            alertas.append("CR não informado.")
        # Adicione outras lógicas de alerta aqui...

        timeline = []
        # Lógica da timeline (exemplo)
        if cliente.comunicacoes:
            ultima_com = max(cliente.comunicacoes, key=lambda c: c.data)
            timeline.append({
                "data": ultima_com.data,
                "tipo": "Comunicação",
                "descricao": ultima_com.assunto,
            })
        # Adicione outras lógicas de timeline aqui...

        return render_template(
            "clientes/detalhe.html",
            cliente=cliente,
            resumo=resumo,
            alertas=alertas,
            timeline=timeline,
            enderecos=cliente.enderecos,
            contatos=cliente.contatos,
            # Constantes para a aba ARMAS
            TIPOS_ARMA=TIPOS_ARMA,
            FUNCIONAMENTO_ARMA=FUNCIONAMENTO_ARMA,
            EMISSORES_CRAF=EMISSORES_CRAF,
            CATEGORIAS_ADQUIRENTE=CATEGORIAS_ADQUIRENTE,
            # Constantes para a aba DOCUMENTOS
            CATEGORIAS_DOCUMENTO=CATEGORIAS_DOCUMENTO,
            EMISSORES_DOCUMENTO=EMISSORES_DOCUMENTO,
        )
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar detalhe do cliente {cliente_id}: {e}")
        flash("Não foi possível carregar os dados do cliente.", "danger")
        return redirect(url_for("clientes.index"))

# ======================
# EDITAR CLIENTE
# ======================
@clientes_bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
def editar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        try:
            # Dados pessoais
            cliente.nome = request.form.get("nome") or None
            cliente.apelido = request.form.get("apelido") or None
            cliente.sexo = request.form.get("sexo") or None
            cliente.data_nascimento = parse_date(request.form.get("data_nascimento"))
            cliente.profissao = request.form.get("profissao") or None
            cliente.estado_civil = request.form.get("estado_civil") or None
            cliente.escolaridade = request.form.get("escolaridade") or None
            cliente.nome_pai = request.form.get("nome_pai") or None
            cliente.nome_mae = request.form.get("nome_mae") or None

            # Documentação
            cliente.documento = request.form.get("documento") or None
            cliente.cr = request.form.get("cr") or None
            cliente.cr_emissor = request.form.get("cr_emissor") or None
            cliente.sigma = request.form.get("sigma") or None
            cliente.sinarm = request.form.get("sinarm") or None
            cliente.razao_social = request.form.get("razao_social") or None

            # ============================
            # Atualizar endereço principal
            # ============================
            cep = request.form.get("cep")
            logradouro = request.form.get("endereco")
            numero = request.form.get("numero")
            complemento = request.form.get("complemento")
            bairro = request.form.get("bairro")
            cidade = request.form.get("cidade")
            estado = request.form.get("estado")

            if cliente.enderecos and len(cliente.enderecos) > 0:
                end = cliente.enderecos[0]
            else:
                end = EnderecoCliente(cliente_id=cliente.id)
                db.session.add(end)

            end.cep = cep or None
            end.logradouro = logradouro or None
            end.numero = numero or None
            end.complemento = complemento or None
            end.bairro = bairro or None
            end.cidade = cidade or None
            end.estado = estado or None
            end.tipo = "residencial"

            # ============================
            # Atualizar contatos principais
            # ============================
            email_val = request.form.get("email")
            tel_val = request.form.get("telefone")
            cel_val = request.form.get("celular")

            tipos = {"email": email_val, "telefone": tel_val, "celular": cel_val}

            for tipo, valor in tipos.items():
                if not valor:
                    continue
                contato_existente = next((c for c in cliente.contatos if c.tipo == tipo), None)
                if contato_existente:
                    contato_existente.valor = valor
                else:
                    db.session.add(ContatoCliente(cliente_id=cliente.id, tipo=tipo, valor=valor))

            # ============================
            # Atualizar categorias / funções
            # ============================
            cliente.cac = "cac" in request.form
            cliente.filiado = "filiado" in request.form
            cliente.policial = "policial" in request.form
            cliente.bombeiro = "bombeiro" in request.form
            cliente.militar = "militar" in request.form
            cliente.iat = "iat" in request.form
            cliente.psicologo = "psicologo" in request.form
            cliente.atirador_n1 = "atirador_n1" in request.form
            cliente.atirador_n2 = "atirador_n2" in request.form
            cliente.atirador_n3 = "atirador_n3" in request.form

            cliente.updated_at = datetime.now()
            db.session.commit()

            flash("Dados do cliente atualizados com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

        except Exception as e:
            db.session.rollback()
            print("Erro ao editar cliente:", e)
            flash(f"Erro ao editar cliente: {e}", "danger")

    return render_template("clientes/editar.html", cliente=cliente)

# ======================
# EXCLUIR CLIENTE
# ======================
@clientes_bp.route("/<int:cliente_id>/excluir", methods=["POST"])
def deletar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    try:
        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente excluído com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir cliente: {e}", "danger")

    return redirect(url_for("clientes.index"))

    # ===============================
    # Resumo de quantidades
    # ===============================
    resumo = {
        "documentos": len(cliente.documentos),
        "armas": len(cliente.armas),
        "comunicacoes": len(cliente.comunicacoes),
        "processos": len(cliente.processos),
        "vendas": len(cliente.vendas),
    }

    # ===============================
    # Alertas inteligentes
    # ===============================
    alertas = []

    # 1️⃣ CR não informado ou vencido
    if not cliente.cr or not cliente.cr_emissor:
        alertas.append("CR não informado.")
    if cliente.data_validade_cr and cliente.data_validade_cr < datetime.now().date():
        alertas.append(
            f"CR vencido em {cliente.data_validade_cr.strftime('%d/%m/%Y')}"
        )

    # 2️⃣ Documentos vencidos
    for doc in cliente.documentos:
        if getattr(doc, "data_validade", None) and doc.data_validade < datetime.now().date():
            alertas.append(
                f"Documento '{doc.tipo or doc.categoria}' vencido em {doc.data_validade.strftime('%d/%m/%Y')}"
            )

    # 3️⃣ Processos em andamento
    for proc in cliente.processos:
        if proc.status and proc.status.lower() not in ["concluído", "finalizado"]:
            alertas.append(f"Processo em andamento: {proc.tipo} ({proc.status})")

    # ===============================
    # Mini Timeline
    # ===============================
    eventos = []

    # Última venda
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

    # Última comunicação
    if cliente.comunicacoes:
        ultima_com = max(cliente.comunicacoes, key=lambda c: c.data)
        eventos.append(
            {
                "data": ultima_com.data,
                "tipo": "Comunicação",
                "descricao": ultima_com.assunto,
            }
        )

    # Último documento
    if cliente.documentos:
        ultimo_doc = max(cliente.documentos, key=lambda d: d.data_upload)
        eventos.append(
            {
                "data": ultimo_doc.data_upload,
                "tipo": "Documento",
                "descricao": ultimo_doc.tipo or ultimo_doc.categoria,
            }
        )

    # Último processo
    if cliente.processos:
        ultimo_proc = max(cliente.processos, key=lambda p: p.data)
        eventos.append(
            {
                "data": ultimo_proc.data,
                "tipo": "Processo",
                "descricao": ultimo_proc.descricao or ultimo_proc.tipo,
            }
        )

    # Ordena e limita timeline
    timeline = sorted(eventos, key=lambda e: e["data"], reverse=True)[:5]

    # ===============================
    # Renderização final
    # ===============================
    return render_template(
        "clientes/detalhe.html",
        cliente=cliente,
        resumo=resumo,
        tipos_arma=TIPOS_ARMA,
        funcionamento_arma=FUNCIONAMENTO_ARMA,
        emissores_craf=EMISSORES_CRAF,
        categorias_adquirente=CATEGORIAS_ADQUIRENTE,
        alertas=alertas,
        CATEGORIAS_DOCUMENTO=CATEGORIAS_DOCUMENTO,
        EMISSORES_DOCUMENTO=EMISSORES_DOCUMENTO,
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

# =========================
# DOCUMENTOS
# =========================
from flask import request, redirect, url_for, render_template, flash, jsonify
from app import db
from app.utils.r2_helpers import gerar_link_r2
# 👇 ALTERAÇÃO APLICADA AQUI (import) 👇
from app.utils.storage import get_s3, get_bucket, deletar_arquivo 
from app.clientes.models import Cliente, Documento
from app.clientes.constants import CATEGORIAS_DOCUMENTO, EMISSORES_DOCUMENTO
from datetime import datetime
from werkzeug.utils import secure_filename
from io import BytesIO


@clientes_bp.route("/<int:cliente_id>/documentos")
def documentos(cliente_id):
    """
    Redireciona para a aba 'documentos' dentro do detalhe do cliente.
    (A listagem é renderizada pelo template principal do cliente.)
    """
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# --- NOVO DOCUMENTO (manual + OCR) ---
@clientes_bp.route("/<int:cliente_id>/documentos/novo", methods=["POST"])
def novo_documento(cliente_id):
    """Criação manual de documento, com upload opcional (manual ou OCR)."""
    cliente = Cliente.query.get_or_404(cliente_id)

    categoria = request.form.get("categoria")
    tipo = categoria or request.form.get("tipo")
    emissor = request.form.get("emissor")
    numero = request.form.get("numero_documento")
    data_emissao = request.form.get("data_emissao")
    data_validade = request.form.get("data_validade")
    validade_indeterminada = bool(request.form.get("validade_indeterminada"))
    observacoes = request.form.get("observacoes")
    caminho_arquivo = request.form.get("caminho_arquivo") or None
    nome_original = request.form.get("arquivo") or None

    # 🔹 Upload manual (se o OCR não enviou caminho)
    if not caminho_arquivo and "arquivo" in request.files and request.files["arquivo"].filename:
        file = request.files["arquivo"]
        nome_seguro = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        caminho_arquivo = f"clientes/{cliente_id}/documentos/{timestamp}_{nome_seguro}"

        s3 = get_s3()
        bucket = get_bucket()
        s3.upload_fileobj(file, bucket, caminho_arquivo)
        nome_original = nome_seguro

    def parse_date(value):
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    documento = Documento(
        cliente_id=cliente.id,
        tipo=tipo,
        categoria=categoria,
        emissor=emissor,
        numero_documento=numero,
        data_emissao=parse_date(data_emissao),
        data_validade=parse_date(data_validade),
        validade_indeterminada=validade_indeterminada,
        observacoes=observacoes,
        caminho_arquivo=caminho_arquivo,
        nome_original=nome_original,
        data_upload=datetime.utcnow(),
    )

    db.session.add(documento)
    db.session.commit()
    flash("Documento cadastrado com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id, _anchor="documentos"))


# --- EDITAR DOCUMENTO (com suporte dinâmico) ---
@clientes_bp.route("/<int:cliente_id>/documentos/<int:doc_id>/editar", methods=["GET", "POST"])
def editar_documento(cliente_id, doc_id):
    documento = Documento.query.get_or_404(doc_id)
    cliente = Cliente.query.get_or_404(cliente_id)  # ✅ necessário para o template

    # GET → retorna o HTML do formulário para o modal dinâmico (AJAX)
    if request.method == "GET":
        return render_template(
            "clientes/abas/documentos_editar.html",
            cliente=cliente,                           # ✅ evita 'cliente is undefined'
            doc=documento,
            CATEGORIAS_DOCUMENTO=CATEGORIAS_DOCUMENTO,
            EMISSORES_DOCUMENTO=EMISSORES_DOCUMENTO,
        )

    # POST → salva alterações
    documento.categoria = request.form.get("categoria")
    documento.tipo = documento.categoria or request.form.get("tipo")
    documento.emissor = request.form.get("emissor")
    documento.numero_documento = request.form.get("numero_documento")
    documento.observacoes = request.form.get("observacoes")
    documento.validade_indeterminada = bool(request.form.get("validade_indeterminada"))

    def parse_date(value):
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    documento.data_emissao = parse_date(request.form.get("data_emissao"))
    documento.data_validade = parse_date(request.form.get("data_validade"))

    # Substituição de arquivo (manual ou OCR)
    novo_caminho = request.form.get("caminho_arquivo")
    field_name = f"arquivoEditar{doc_id}"
    if field_name in request.files and request.files[field_name].filename:
        file = request.files[field_name]
        nome_seguro = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        novo_caminho = f"clientes/{cliente_id}/documentos/{timestamp}_{nome_seguro}"

        s3 = get_s3()
        bucket = get_bucket()
        file.seek(0)
        s3.upload_fileobj(file, bucket, novo_caminho)
        documento.nome_original = nome_seguro

    if novo_caminho:
        documento.caminho_arquivo = novo_caminho
        documento.data_upload = datetime.utcnow()

    db.session.commit()
    flash("Documento atualizado com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# --- DELETAR DOCUMENTO ---
@clientes_bp.route("/<int:cliente_id>/documentos/<int:doc_id>/deletar", methods=["POST"])
def deletar_documento(cliente_id, doc_id):
    # 👇 ALTERAÇÃO APLICADA AQUI (lógica inteira da função) 👇
    documento = Documento.query.get_or_404(doc_id)
    
    # Guarda o caminho do arquivo antes de deletar o objeto
    caminho_arquivo_para_deletar = documento.caminho_arquivo

    try:
        db.session.delete(documento)
        db.session.commit()
        
        # Se a deleção no DB foi bem-sucedida, deleta o arquivo no R2
        if caminho_arquivo_para_deletar:
            deletar_arquivo(caminho_arquivo_para_deletar)
            
        flash("Documento removido com sucesso!", "info")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao deletar documento {doc_id}: {e}")
        flash("Erro ao remover o documento.", "danger")
        
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# --- ABRIR DOCUMENTO (R2) ---
@clientes_bp.route("/documentos/<int:doc_id>/abrir")
def abrir_documento(doc_id):
    """Gera link pré-assinado para abrir documento armazenado no R2."""
    documento = Documento.query.get_or_404(doc_id)
    if not documento.caminho_arquivo:
        flash("Nenhum arquivo enviado para este documento.", "warning")
        return redirect(request.referrer or url_for("clientes.index"))

    try:
        link = gerar_link_r2(documento.caminho_arquivo)
        return redirect(link)
    except Exception as e:
        flash(f"Erro ao gerar link do arquivo: {e}", "danger")
        return redirect(request.referrer or url_for("clientes.index"))

# ======================
# ARMAS
# ======================

@clientes_bp.route("/<int:cliente_id>/armas", methods=["GET"])
def cliente_armas(cliente_id):
    """Redireciona para a aba 'armas' dentro do detalhe do cliente"""
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


# ----------------------
# FORMULÁRIO NOVA ARMA (GET - usado no modal)
# ----------------------
@clientes_bp.route("/<int:cliente_id>/armas/nova", methods=["GET"])
def form_nova_arma(cliente_id):
    """Renderiza o modal para cadastro de nova arma"""
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template(
        "clientes/abas/armas_nova.html",
        cliente=cliente,
        TIPOS_ARMA=TIPOS_ARMA,
        FUNCIONAMENTO_ARMA=FUNCIONAMENTO_ARMA,
        EMISSORES_CRAF=EMISSORES_CRAF,
        CATEGORIAS_ADQUIRENTE=CATEGORIAS_ADQUIRENTE,
    )


# ----------------------
# NOVA ARMA (POST - cadastro manual ou com arquivo opcional)
# ----------------------
@clientes_bp.route("/<int:cliente_id>/armas/nova", methods=["POST"])
def nova_arma(cliente_id):
    """Cadastro manual de arma, com upload opcional de arquivo."""
    num_serie = request.form.get("numero_serie")
    if num_serie and Arma.query.filter_by(numero_serie=num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    tipo = request.form.get("tipo") or None
    funcionamento = request.form.get("funcionamento") or None
    marca = request.form.get("marca") or None
    modelo = request.form.get("modelo") or None
    calibre = request.form.get("calibre") or None
    emissor_craf = request.form.get("emissor_craf") or None
    numero_sigma = request.form.get("numero_sigma") or None
    categoria_adquirente = request.form.get("categoria_adquirente") or None
    validade_indeterminada = bool(request.form.get("validade_indeterminada"))
    data_validade = request.form.get("data_validade_craf") or None

    from datetime import datetime
    data_validade_parsed = None
    if data_validade:
        try:
            data_validade_parsed = datetime.strptime(data_validade, "%Y-%m-%d").date()
        except ValueError:
            data_validade_parsed = None

    # upload opcional de arquivo (R2)
    caminho = None
    if "arquivo" in request.files and request.files["arquivo"].filename:
        file = request.files["arquivo"]
        nome_seguro = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        caminho = f"clientes/{cliente_id}/armas/{timestamp}_{nome_seguro}"
        # salva no R2
        s3.upload_fileobj(file, R2_BUCKET, caminho)

    arma = Arma(
        cliente_id=cliente_id,
        tipo=tipo,
        funcionamento=funcionamento,
        marca=marca,
        modelo=modelo,
        calibre=calibre,
        numero_serie=num_serie,
        emissor_craf=emissor_craf,
        numero_sigma=numero_sigma,
        categoria_adquirente=categoria_adquirente,
        validade_indeterminada=validade_indeterminada,
        data_validade_craf=data_validade_parsed,
        caminho_craf=caminho,
    )

    db.session.add(arma)
    db.session.commit()

    flash("Arma cadastrada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


# ----------------------
# FORMULÁRIO EDITAR ARMA (GET - usado no modal)
# ----------------------
@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/editar", methods=["GET"])
def form_editar_arma(cliente_id, arma_id):
    """Renderiza o modal para edição da arma"""
    cliente = Cliente.query.get_or_404(cliente_id)
    arma = Arma.query.get_or_404(arma_id)
    return render_template(
        "clientes/abas/armas_editar.html",
        cliente=cliente,
        arma=arma,
        TIPOS_ARMA=TIPOS_ARMA,
        FUNCIONAMENTO_ARMA=FUNCIONAMENTO_ARMA,
        EMISSORES_CRAF=EMISSORES_CRAF,
        CATEGORIAS_ADQUIRENTE=CATEGORIAS_ADQUIRENTE,
    )


# ----------------------
# EDITAR ARMA (POST - com valida duplicidade e substituição de arquivo)
# ----------------------
@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/editar", methods=["POST"])
def editar_arma(cliente_id, arma_id):
    """Edita os dados de uma arma existente."""
    arma = Arma.query.get_or_404(arma_id)

    # valida duplicidade de número de série
    num_serie = request.form.get("numero_serie")
    if num_serie and Arma.query.filter(Arma.id != arma.id, Arma.numero_serie == num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    arma.tipo = request.form.get("tipo") or None
    arma.funcionamento = request.form.get("funcionamento") or None
    arma.marca = request.form.get("marca") or None
    arma.modelo = request.form.get("modelo") or None
    arma.calibre = request.form.get("calibre") or None
    arma.numero_serie = num_serie or None
    arma.emissor_craf = request.form.get("emissor_craf") or None
    arma.numero_sigma = request.form.get("numero_sigma") or None
    arma.categoria_adquirente = request.form.get("categoria_adquirente") or None
    arma.validade_indeterminada = bool(request.form.get("validade_indeterminada"))

    from datetime import datetime
    data_validade = request.form.get("data_validade_craf") or None
    if data_validade:
        try:
            arma.data_validade_craf = datetime.strptime(data_validade, "%Y-%m-%d").date()
        except ValueError:
            arma.data_validade_craf = None
    else:
        arma.data_validade_craf = None

    # substituição de arquivo (upload manual para o R2)
    if "arquivo" in request.files and request.files["arquivo"].filename:
        file = request.files["arquivo"]
        nome_seguro = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        arma.caminho_craf = f"clientes/{cliente_id}/armas/{timestamp}_{nome_seguro}"
        s3.upload_fileobj(file, R2_BUCKET, arma.caminho_craf)

    # substituição de caminho vindo via OCR (hidden input)
    caminho = request.form.get("caminho_craf") or None
    if caminho:
        arma.caminho_craf = caminho

    db.session.commit()
    flash("Arma atualizada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

# ----------------------
# SALVAR CRAF (via OCR)
# ----------------------
@clientes_bp.route("/<int:cliente_id>/armas/salvar", methods=["POST"])
def salvar_craf(cliente_id):
    """Cria nova arma a partir do OCR do CRAF"""
    num_serie = request.form.get("numero_serie")
    if num_serie and Arma.query.filter_by(numero_serie=num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    tipo = request.form.get("tipo") or None
    funcionamento = request.form.get("funcionamento") or None
    marca = request.form.get("marca") or None
    modelo = request.form.get("modelo") or None
    calibre = request.form.get("calibre") or None
    numero_serie = num_serie or None
    emissor_craf = request.form.get("emissor_craf") or None
    numero_sigma = request.form.get("numero_sigma") or None
    categoria_adquirente = request.form.get("categoria_adquirente") or None
    validade_indeterminada = bool(request.form.get("validade_indeterminada"))
    data_validade = request.form.get("data_validade_craf") or None
    caminho = request.form.get("caminho_craf") or None

    from datetime import datetime
    data_validade_parsed = None
    if data_validade:
        try:
            data_validade_parsed = datetime.strptime(data_validade, "%Y-%m-%d").date()
        except ValueError:
            data_validade_parsed = None

    arma = Arma(
        cliente_id=cliente_id,
        tipo=tipo,
        funcionamento=funcionamento,
        marca=marca,
        modelo=modelo,
        calibre=calibre,
        numero_serie=numero_serie,
        emissor_craf=emissor_craf,
        numero_sigma=numero_sigma,
        categoria_adquirente=categoria_adquirente,
        validade_indeterminada=validade_indeterminada,
        data_validade_craf=data_validade_parsed,
        caminho_craf=caminho,
    )
    db.session.add(arma)
    db.session.commit()

    flash("Arma cadastrada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


# ----------------------
# DELETAR ARMA
# ----------------------
@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/deletar", methods=["POST"])
def deletar_arma(cliente_id, arma_id):
    """Deleta arma do cliente."""
    arma = Arma.query.get_or_404(arma_id)
    db.session.delete(arma)
    db.session.commit()
    flash("Arma excluída com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


# ----------------------
# ABRIR CRAF
# ----------------------
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