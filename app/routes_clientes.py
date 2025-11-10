# app/routes_clientes.py

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import Cliente, Documento
from app.vendas.models import Venda
from app.services.storage import upload_file, delete_file  # helper para R2
from werkzeug.utils import secure_filename

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

# =====================================================
# Listar clientes
# =====================================================
@clientes_bp.route("/", methods=["GET"])
@login_required
def lista():
    query = Cliente.query
    nome = request.args.get("nome", "").strip()
    documento = request.args.get("documento", "").strip()

    if nome:
        query = query.filter(Cliente.nome.ilike(f"%{nome}%"))
    if documento:
        query = query.filter(Cliente.documento.ilike(f"%{documento}%"))

    todos_clientes = query.order_by(Cliente.nome.asc()).all()
    return render_template("clientes/lista.html", clientes=todos_clientes)


# =====================================================
# Detalhe do cliente
# =====================================================
@clientes_bp.route("/<int:cliente_id>")
@login_required
def detalhe(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    vendas = Venda.query.filter_by(cliente_id=cliente.id).order_by(Venda.data_abertura.desc()).all()
    documentos = Documento.query.filter_by(cliente_id=cliente.id).all()
    return render_template("clientes/detalhe.html", cliente=cliente, vendas=vendas, documentos=documentos)


# =====================================================
# Criar/Editar Cliente
# =====================================================
@clientes_bp.route("/novo", methods=["GET", "POST"])
@clientes_bp.route("/editar/<int:cliente_id>", methods=["GET", "POST"])
@login_required
def gerenciar(cliente_id=None):
    cliente = Cliente.query.get(cliente_id) if cliente_id else None
    if request.method == "POST":
        if not cliente:
            cliente = Cliente()
            db.session.add(cliente)

        # ==== Dados básicos ====
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
        cliente.cr = request.form.get("cr")
        cliente.cr_emissor = request.form.get("cr_emissor")
        cliente.sigma = request.form.get("sigma")
        cliente.sinarm = request.form.get("sinarm")

        # Perfis (checkbox → boolean)
        cliente.cac = bool(request.form.get("cac"))
        cliente.filiado = bool(request.form.get("filiado"))
        cliente.policial = bool(request.form.get("policial"))
        cliente.bombeiro = bool(request.form.get("bombeiro"))
        cliente.militar = bool(request.form.get("militar"))
        cliente.iat = bool(request.form.get("iat"))
        cliente.psicologo = bool(request.form.get("psicologo"))
        cliente.sinarm = bool(request.form.get("sinarm"))

        db.session.commit()

        flash("Cliente salvo com sucesso!", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

    return render_template("clientes/form.html", cliente=cliente)


# =====================================================
# Upload de documento (rota separada)
# =====================================================
@clientes_bp.route("/<int:cliente_id>/documento/upload", methods=["POST"])
@login_required
def upload_documento(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if "arquivo" not in request.files:
        flash("Nenhum arquivo enviado!", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

    file = request.files["arquivo"]
    if file and file.filename:
        filename = secure_filename(file.filename)
        url = upload_file(file, filename)
        doc = Documento(
            cliente_id=cliente.id,
            tipo=request.form.get("tipo") or "OUTRO",
            nome_original=filename,
            caminho_arquivo=url,
            mime_type=file.mimetype,
        )
        db.session.add(doc)
        db.session.commit()
        flash("Documento enviado com sucesso!", "success")
    else:
        flash("Arquivo inválido!", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


# =====================================================
# Excluir documento
# =====================================================
@clientes_bp.route("/documento/<int:doc_id>/excluir", methods=["POST"])
@login_required
def excluir_documento(doc_id):
    doc = Documento.query.get_or_404(doc_id)
    delete_file(doc.caminho_arquivo)  # remove do R2
    db.session.delete(doc)
    db.session.commit()
    flash("Documento excluído!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=doc.cliente_id))


# =====================================================
# Excluir cliente
# =====================================================
@clientes_bp.route("/excluir/<int:cliente_id>", methods=["POST"])
@login_required
def excluir(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for("clientes.lista"))


# =========================
# API: Buscar endereço pelo CEP
# =========================
@clientes_bp.route("/api/cep/<cep>", methods=["GET"])
@login_required
def api_cep(cep):
    import requests
    cep = cep.replace("-", "").strip()
    if len(cep) != 8:
        return {"erro": "CEP inválido"}, 400

    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
        if r.status_code == 200:
            dados = r.json()
            if "erro" in dados:
                return {"erro": "CEP não encontrado"}, 404
            return {
                "logradouro": dados.get("logradouro", ""),
                "bairro": dados.get("bairro", ""),
                "cidade": dados.get("localidade", ""),
                "estado": dados.get("uf", ""),
            }
        return {"erro": "Falha ao consultar ViaCEP"}, 500
    except Exception as e:
        return {"erro": str(e)}, 500


# =========================
# API: Buscar dados pelo CNPJ
# =========================
@clientes_bp.route("/api/cnpj/<cnpj>", methods=["GET"])
@login_required
def api_cnpj(cnpj):
    import requests
    cnpj = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()
    if len(cnpj) != 14:
        return {"erro": "CNPJ inválido"}, 400

    try:
        r = requests.get(f"https://receitaws.com.br/v1/cnpj/{cnpj}")
        if r.status_code == 200:
            return r.json()
        return {"erro": "Falha ao consultar ReceitaWS"}, 500
    except Exception as e:
        return {"erro": str(e)}, 500
