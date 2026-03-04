# app/loja/routes_auth.py
"""
Rotas de autenticação EXCLUSIVAS do e-commerce.
Registradas no loja_bp — nunca conflitam com o login administrativo.
"""

import os
from datetime import date
from flask import render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from app import db
from app.loja import loja_bp
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente, Documento
from app.loja.auth_loja import logar_cliente, deslogar_cliente, get_cliente_logado, cliente_logado_required
from app.utils.datetime import now_local

UPLOAD_PASTA = os.path.join('app', 'static', 'uploads', 'documentos_clientes')
EXTENSOES_PERMITIDAS = {'pdf', 'jpg', 'jpeg', 'png'}


def _extensao_ok(nome):
    return '.' in nome and nome.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS


# ──────────────────────────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_cliente_logado():
        return redirect(url_for("loja.minha_conta"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("password") or ""

        cliente = Cliente.query.filter_by(email_login=email).first()

        if not cliente:
            flash("E-mail não encontrado.", "danger")
            return render_template("loja/auth/login.html")

        if not cliente.ativo_loja:
            flash("Conta desativada. Entre em contato com a loja.", "danger")
            return render_template("loja/auth/login.html")

        if not cliente.check_senha(senha):
            flash("Senha incorreta.", "danger")
            return render_template("loja/auth/login.html")

        logar_cliente(cliente)
        flash(f"Bem-vindo, {cliente.nome.split()[0]}!", "success")

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/loja"):
            return redirect(next_url)
        return redirect(url_for("loja.minha_conta"))

    return render_template("loja/auth/login.html")


# ──────────────────────────────────────────────────────────────────
# CADASTRO
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if get_cliente_logado():
        return redirect(url_for("loja.minha_conta"))

    if request.method == "POST":
        nome     = (request.form.get("nome") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()
        cpf      = (request.form.get("documento") or "").strip()
        senha    = request.form.get("password") or ""
        confirma = request.form.get("password_confirm") or ""

        if not nome or not email or not cpf or not senha:
            flash("Preencha todos os campos obrigatórios.", "warning")
            return render_template("loja/auth/cadastro.html")

        if len(senha) < 8:
            flash("A senha deve ter pelo menos 8 caracteres.", "warning")
            return render_template("loja/auth/cadastro.html")

        if senha != confirma:
            flash("As senhas não coincidem.", "warning")
            return render_template("loja/auth/cadastro.html")

        if Cliente.query.filter_by(email_login=email).first():
            flash("Este e-mail já está cadastrado.", "warning")
            return render_template("loja/auth/cadastro.html")

        cliente = None
        cpf_digits = "".join(filter(str.isdigit, cpf))
        if cpf_digits:
            cliente = Cliente.query.filter_by(documento=cpf_digits).first()
            if not cliente:
                cliente = Cliente.query.filter(
                    Cliente.documento.in_([cpf, cpf_digits])
                ).first()

        if cliente:
            if cliente.email_login:
                flash("Este CPF já possui uma conta na loja.", "warning")
                return render_template("loja/auth/cadastro.html")
            cliente.email_login    = email
            cliente.loja_criado_em = now_local()
        else:
            cliente = Cliente(
                nome=nome,
                documento=cpf_digits or None,
                email_login=email,
                ativo_loja=True,
                loja_criado_em=now_local(),
                created_at=now_local(),
                updated_at=now_local(),
            )
            db.session.add(cliente)
            db.session.flush()

            db.session.add(ContatoCliente(
                cliente_id=cliente.id,
                tipo="email",
                valor=email,
            ))

        cliente.set_senha(senha)
        cliente.ativo_loja = True
        db.session.commit()

        logar_cliente(cliente)
        flash("Conta criada com sucesso! Bem-vindo à M4 Tática.", "success")
        return redirect(url_for("loja.minha_conta"))

    return render_template("loja/auth/cadastro.html")


# ──────────────────────────────────────────────────────────────────
# LOGOUT
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/logout")
def logout():
    deslogar_cliente()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("loja.index"))


# ──────────────────────────────────────────────────────────────────
# MINHA CONTA (dashboard)
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/minha-conta")
@cliente_logado_required
def minha_conta():
    cliente = get_cliente_logado()
    return render_template("loja/cliente/dashboard.html", cliente_loja=cliente)


# ──────────────────────────────────────────────────────────────────
# MEUS PEDIDOS
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/meus-pedidos")
@cliente_logado_required
def meus_pedidos():
    cliente = get_cliente_logado()
    vendas = sorted(
        cliente.vendas or [],
        key=lambda v: v.data_abertura,
        reverse=True
    )
    return render_template("loja/cliente/pedidos.html", vendas=vendas)


# ──────────────────────────────────────────────────────────────────
# ENDEREÇOS
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/meus-enderecos")
@cliente_logado_required
def meus_enderecos():
    cliente = get_cliente_logado()
    return render_template("loja/cliente/enderecos.html", enderecos=cliente.enderecos or [])


@loja_bp.route("/meus-enderecos/novo", methods=["POST"])
@cliente_logado_required
def novo_endereco():
    cliente = get_cliente_logado()
    endereco = EnderecoCliente(
        cliente_id  = cliente.id,
        tipo        = (request.form.get("tipo") or "residencial").strip(),
        cep         = (request.form.get("cep") or "").strip(),
        logradouro  = (request.form.get("logradouro") or "").strip(),
        numero      = (request.form.get("numero") or "").strip(),
        complemento = (request.form.get("complemento") or "").strip() or None,
        bairro      = (request.form.get("bairro") or "").strip(),
        cidade      = (request.form.get("cidade") or "").strip(),
        estado      = (request.form.get("estado") or "").strip().upper(),
    )
    db.session.add(endereco)
    db.session.commit()
    flash("Endereço adicionado com sucesso!", "success")
    return redirect(url_for("loja.meus_enderecos"))


@loja_bp.route("/meus-enderecos/<int:endereco_id>/editar", methods=["POST"])
@cliente_logado_required
def editar_endereco(endereco_id):
    cliente  = get_cliente_logado()
    endereco = EnderecoCliente.query.filter_by(id=endereco_id, cliente_id=cliente.id).first_or_404()

    endereco.tipo        = (request.form.get("tipo") or "residencial").strip()
    endereco.cep         = (request.form.get("cep") or "").strip()
    endereco.logradouro  = (request.form.get("logradouro") or "").strip()
    endereco.numero      = (request.form.get("numero") or "").strip()
    endereco.complemento = (request.form.get("complemento") or "").strip() or None
    endereco.bairro      = (request.form.get("bairro") or "").strip()
    endereco.cidade      = (request.form.get("cidade") or "").strip()
    endereco.estado      = (request.form.get("estado") or "").strip().upper()

    db.session.commit()
    flash("Endereço atualizado.", "success")
    return redirect(url_for("loja.meus_enderecos"))


@loja_bp.route("/meus-enderecos/<int:endereco_id>/excluir", methods=["POST"])
@cliente_logado_required
def excluir_endereco(endereco_id):
    cliente  = get_cliente_logado()
    endereco = EnderecoCliente.query.filter_by(id=endereco_id, cliente_id=cliente.id).first_or_404()
    db.session.delete(endereco)
    db.session.commit()
    flash("Endereço removido.", "info")
    return redirect(url_for("loja.meus_enderecos"))


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — listar
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/meus-documentos")
@cliente_logado_required
def meus_documentos():
    cliente = get_cliente_logado()
    documentos = (
        Documento.query
        .filter_by(cliente_id=cliente.id)
        .order_by(Documento.created_at.desc())
        .all()
    )
    return render_template("loja/cliente/documentos.html", documentos=documentos)


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — upload
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/meus-documentos/upload", methods=["POST"])
@cliente_logado_required
def upload_documento():
    cliente = get_cliente_logado()
    arquivo = request.files.get("arquivo")

    if not arquivo or arquivo.filename == "":
        flash("Selecione um arquivo.", "warning")
        return redirect(url_for("loja.meus_documentos"))

    if not _extensao_ok(arquivo.filename):
        flash("Formato não permitido. Use PDF, JPG ou PNG.", "warning")
        return redirect(url_for("loja.meus_documentos"))

    # Salva o arquivo
    os.makedirs(UPLOAD_PASTA, exist_ok=True)
    nome_seguro = secure_filename(arquivo.filename)
    nome_final  = f"cliente_{cliente.id}_{now_local().strftime('%Y%m%d%H%M%S')}_{nome_seguro}"
    caminho     = os.path.join(UPLOAD_PASTA, nome_final)
    arquivo.save(caminho)

    # Converte datas
    def parse_date(campo):
        val = request.form.get(campo, "").strip()
        if val:
            try:
                return date.fromisoformat(val)
            except ValueError:
                pass
        return None

    validade_indet = bool(request.form.get("validade_indeterminada"))

    doc = Documento(
        cliente_id            = cliente.id,
        tipo                  = (request.form.get("tipo") or "Outro").strip(),
        numero_documento      = (request.form.get("numero_documento") or "").strip() or None,
        data_emissao          = parse_date("data_emissao"),
        data_validade         = None if validade_indet else parse_date("data_validade"),
        validade_indeterminada= validade_indet,
        observacoes           = (request.form.get("observacoes") or "").strip() or None,
        nome_original         = arquivo.filename,
        caminho_arquivo       = caminho,
        mime_type             = arquivo.mimetype,
    )
    db.session.add(doc)
    db.session.commit()

    flash("Documento enviado com sucesso!", "success")
    return redirect(url_for("loja.meus_documentos"))


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — download (só o próprio cliente pode baixar)
# ──────────────────────────────────────────────────────────────────
@loja_bp.route("/meus-documentos/<int:doc_id>/baixar")
@cliente_logado_required
def baixar_documento(doc_id):
    cliente = get_cliente_logado()
    doc = Documento.query.filter_by(id=doc_id, cliente_id=cliente.id).first_or_404()

    if not doc.caminho_arquivo or not os.path.exists(doc.caminho_arquivo):
        flash("Arquivo não encontrado.", "danger")
        return redirect(url_for("loja.meus_documentos"))

    return send_file(
        doc.caminho_arquivo,
        download_name=doc.nome_original or f"documento_{doc.id}",
        as_attachment=True
    )


# ──────────────────────────────────────────────────────────────────
# CONTEXT PROCESSOR
# ──────────────────────────────────────────────────────────────────
@loja_bp.app_context_processor
def inject_cliente_loja():
    return {"cliente_loja": get_cliente_logado()}