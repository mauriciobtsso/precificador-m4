from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    send_file, jsonify, current_app
)
from flask_login import login_user, logout_user, login_required
from sqlalchemy import func, extract, case, text
from datetime import datetime, timedelta
from decimal import Decimal
from io import TextIOWrapper
import csv, os

# =========================
# Imports do projeto
# =========================
from app.main import main
from app.extensions import db
from app.config import get_config
from app.services.importacao import importar_clientes, importar_vendas
from app.services.parcelamento import gerar_linhas_por_valor, gerar_linhas_por_produto
from app.utils.pdf_helpers import gerar_pdf_pedido
from app.utils.whatsapp_helpers import gerar_texto_whatsapp
from app.utils.number_helpers import to_float
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.vendas.models import Venda, ItemVenda
from app.clientes.models import Cliente
from app.models import (
    User,
    PedidoCompra, ItemPedido, Taxa, Notificacao
)
from app.clientes.models import Cliente
from app.services.dashboard_service import (
    get_dashboard_context,
    get_dashboard_resumo,
    get_dashboard_timeline
)

from flask import Response, stream_with_context, abort
import mimetypes
from app.utils.storage import get_s3, get_bucket

# =====================================================
# Rotas principais
# =====================================================
@main.route("/")
def index():
    return redirect(url_for("main.dashboard"))

# --- Login ---
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))
        else:
            flash("Usuário ou senha inválidos", "danger")
    return render_template("login.html")

# --- Logout ---
@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("main.login"))

# ===========================================================
# DASHBOARD PRINCIPAL (visão tradicional)
# ===========================================================
@main.route("/dashboard")
@login_required
def dashboard():
    context = get_dashboard_context()
    return render_template("dashboard.html", **context)

# ============================================================
# APIs do Dashboard (Resumo e Timeline)
# ============================================================

from flask import jsonify

@main.route("/dashboard/api/resumo")
@login_required
def dashboard_api_resumo():
    try:
        data = get_dashboard_resumo()
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Erro no dashboard_api_resumo: {e}")
        return jsonify({"error": str(e)}), 500


@main.route("/dashboard/api/timeline")
@login_required
def dashboard_api_timeline():
    try:
        data = get_dashboard_timeline()
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Erro no dashboard_api_timeline: {e}")
        return jsonify({"error": str(e)}), 500


# ===========================================================
# Parcelamento / Configurações / Usuários / Health / Importar
# ===========================================================
@main.route("/parcelamento")
@login_required
def parcelamento_index():
    produtos = Produto.query.order_by(Produto.nome).all()
    return render_template("parcelamento_index.html", produtos=produtos)

@main.route("/parcelamento/<int:produto_id>")
@login_required
def parcelamento(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    valor_base, linhas = gerar_linhas_por_produto(produto)
    texto_whats = gerar_texto_whatsapp(produto, valor_base, linhas)
    return render_template(
        "parcelamento.html",
        produto=produto,
        resultado=linhas,
        texto_whats=texto_whats,
        Decimal=Decimal
    )

@main.route("/parcelamento/rapido", methods=["GET", "POST"])
@login_required
def parcelamento_rapido():
    resultado, preco_base, texto_whats = [], None, ""
    if request.method == "POST":
        preco_base = to_float(request.form.get("preco_base"))
        taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
        resultado = gerar_linhas_por_valor(preco_base)
        texto_whats = gerar_texto_whatsapp(None, preco_base, resultado)
    return render_template("parcelamento_rapido.html",
                           resultado=resultado, preco_base=preco_base, texto_whats=texto_whats)

# --- Configurações ---
#@main.route("/configuracoes")
#@login_required
#def configuracoes():
#    configs = Configuracao.query.all()
#    return render_template("configuracoes.html", configs=configs)

#@main.route("/configuracao/nova", methods=["GET", "POST"])
#@main.route("/configuracao/editar/<int:config_id>", methods=["GET", "POST"])
#@login_required
#def gerenciar_configuracao(config_id=None):
#    config = Configuracao.query.get(config_id) if config_id else None
#    if request.method == "POST":
#        chave, valor = request.form.get("chave"), request.form.get("valor")
#        if not config:
#            config = Configuracao(chave=chave, valor=valor)
#            db.session.add(config)
#        else:
#            config.chave, config.valor = chave, valor
#        db.session.commit()
#        flash("Configuração salva com sucesso!", "success")
#        return redirect(url_for("main.configuracoes"))
#    return render_template("configuracao_form.html", config=config)

#@main.route("/configuracao/excluir/<int:config_id>")
#@login_required
#def excluir_configuracao(config_id):
#    config = Configuracao.query.get_or_404(config_id)
#    db.session.delete(config)
#    db.session.commit()
#    flash("Configuração excluída com sucesso!", "success")
#    return redirect(url_for("main.configuracoes"))

# --- Usuários ---
#@main.route("/usuarios")
#@login_required
#def usuarios():
#    users = User.query.all()
#    return render_template("usuarios.html", users=users)
#
#@main.route("/usuario/novo", methods=["GET", "POST"])
#@main.route("/usuario/editar/<int:user_id>", methods=["GET", "POST"])
#@login_required
#def gerenciar_usuario(user_id=None):
#    user = User.query.get(user_id) if user_id else None
#    if request.method == "POST":
#        username, password = request.form.get("username"), request.form.get("password")
#        if not user:
#            user = User(username=username, password=password)
#            db.session.add(user)
#        else:
#            user.username = username
#            if password:
#                user.password = password
#        db.session.commit()
#        flash("Usuário salvo com sucesso!", "success")
#        return redirect(url_for("main.usuarios"))
#    return render_template("usuario_form.html", user=user)

#@main.route("/usuario/excluir/<int:user_id>")
#@login_required
#def excluir_usuario(user_id):
#    user = User.query.get_or_404(user_id)
#    db.session.delete(user)
#    db.session.commit()
#    flash("Usuário excluído com sucesso!", "success")
#    return redirect(url_for("main.usuarios"))

# --- Health Check ---
@main.route("/health", methods=["GET", "HEAD"])
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error", "msg": str(e)}, 500

# --- Importar Relatórios ---
@main.route("/importar", methods=["GET", "POST"])
@login_required
def importar():
    if request.method == "POST":
        file, tipo = request.files.get("file"), request.form.get("tipo")
        if not file or file.filename == "":
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(url_for("main.importar"))
        try:
            if str(file.filename).lower().endswith(".xlsx"):
                if tipo == "clientes":
                    importar_clientes(file)
                    flash("Clientes importados com sucesso!", "success")
                elif tipo == "vendas":
                    importar_vendas(file)
                    flash("Vendas importadas com sucesso!", "success")
                else:
                    flash("Tipo de importação inválido.", "danger")
            else:
                flash("Envie um arquivo .xlsx exportado do sistema.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao importar: {e}", "danger")
        return redirect(url_for("main.importar"))
    return render_template("importar.html")

# --- PDF do Pedido ---
@main.route("/pedidos/<int:id>/pdf")
@login_required
def pedido_pdf(id):
    pedido = PedidoCompra.query.get_or_404(id)
    filepath = gerar_pdf_pedido(pedido)
    return send_file(filepath, as_attachment=False)

# --- API WhatsApp ---
@main.route("/api/produto/<int:produto_id>/whatsapp")
@login_required
def api_produto_whatsapp(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    valor_base, linhas = gerar_linhas_por_produto(produto)
    texto_whats = gerar_texto_whatsapp(produto, valor_base, linhas)
    return jsonify({"texto_completo": texto_whats})

# ============================================================
# PROXY DE IMAGEM (NOVA ROTA - ADICIONE ISSO)
# ============================================================
@main.route("/imagem-proxy")
@login_required
def imagem_proxy():
    """
    Baixa a imagem do R2 pelo backend e serve para o frontend.
    """
    key = request.args.get("key")
    if not key:
        return abort(404)

    try:
        s3 = get_s3()
        bucket = get_bucket()

        # CORREÇÃO: Remove o nome do bucket se ele vier "grudado" no início da chave
        # Ex: de "meu-bucket/produtos/foto.jpg" para "produtos/foto.jpg"
        if key.startswith(f"{bucket}/"):
            key = key[len(bucket)+1:]
        
        # Obtém o objeto do R2
        file_obj = s3.get_object(Bucket=bucket, Key=key)
        
        content_type = file_obj.get('ContentType') or mimetypes.guess_type(key)[0] or 'application/octet-stream'
        
        return Response(
            stream_with_context(file_obj['Body'].iter_chunks()),
            content_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        current_app.logger.error(f"Erro no proxy de imagem: {e}")
        return redirect("/static/img/placeholder.jpg")

# --- Context Processor Global ---
@main.app_context_processor
def inject_notificacoes():
    try:
        total_nao_lidas = Notificacao.query.filter_by(status="enviado").count()
    except Exception:
        total_nao_lidas = 0
    return {"total_nao_lidas": total_nao_lidas}
