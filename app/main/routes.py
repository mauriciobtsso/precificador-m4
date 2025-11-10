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
    User, Configuracao,
    PedidoCompra, ItemPedido, Taxa, Notificacao
)
from app.clientes.models import Cliente

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
    hoje = datetime.today()

    produtos = Produto.query.all()
    total_vendas_mes = (
        db.session.query(func.sum(Venda.valor_total))
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .scalar() or 0
    )
    ticket_medio = (
        db.session.query(func.sum(Venda.valor_total) / func.count(Venda.id))
        .scalar() or 0
    )

    top_clientes = (
        db.session.query(Cliente.nome, func.sum(Venda.valor_total).label("total"))
        .join(Venda, Cliente.id == Venda.cliente_id)
        .group_by(Cliente.id)
        .order_by(func.sum(Venda.valor_total).desc())
        .limit(5)
        .all()
    )

    produto_mais_vendido = (
        db.session.query(ItemVenda.produto_nome, func.sum(ItemVenda.quantidade).label("qtd"))
        .group_by(ItemVenda.produto_nome)
        .order_by(func.sum(ItemVenda.quantidade).desc())
        .first()
    )

    vendas_por_mes = (
        db.session.query(
            extract("month", Venda.data_abertura).label("mes"),
            func.sum(Venda.valor_total).label("total"),
        )
        .filter(Venda.data_abertura >= hoje - timedelta(days=180))
        .group_by(extract("month", Venda.data_abertura))
        .order_by(extract("month", Venda.data_abertura))
        .all()
    )

    mapa_meses = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez"
    ]
    meses_nomes = [mapa_meses[int(m) - 1] for m, _ in vendas_por_mes]
    totais = [float(total) for _, total in vendas_por_mes]

    notificacoes_pendentes = Notificacao.query.filter_by(status="enviado").count()

    return render_template(
        "dashboard.html",
        produtos=produtos,
        total_vendas_mes=total_vendas_mes,
        top_clientes=top_clientes,
        produto_mais_vendido=produto_mais_vendido,
        ticket_medio=ticket_medio,
        meses=meses_nomes,
        totais=totais,
        notificacoes_pendentes=notificacoes_pendentes,
    )

# ============================================================
# APIs do Dashboard (Resumo e Timeline)
# ============================================================

from flask import jsonify

@main.route("/dashboard/api/resumo")
@login_required
def dashboard_api_resumo():
    """Retorna dados agregados para os KPIs e gráficos."""
    try:
        # Totais básicos
        total_produtos = db.session.query(func.count(Produto.id)).scalar() or 0
        total_clientes = db.session.query(func.count(Cliente.id)).scalar() or 0

        # Documentos (simples: ativos e vencidos)
        documentos_validos = db.session.query(func.count(Venda.id))\
            .filter(Venda.data_fechamento >= datetime.today() - timedelta(days=365)).scalar() or 0
        documentos_vencidos = db.session.query(func.count(Venda.id))\
            .filter(Venda.data_fechamento < datetime.today() - timedelta(days=365)).scalar() or 0

        # Vendas e ticket médio
        vendas_mes = (
            db.session.query(func.sum(Venda.valor_total))
            .filter(extract("month", Venda.data_abertura) == datetime.today().month)
            .filter(extract("year", Venda.data_abertura) == datetime.today().year)
            .scalar()
            or 0
        )

        ticket_medio = (
            db.session.query(func.sum(Venda.valor_total) / func.count(Venda.id))
            .filter(extract("month", Venda.data_abertura) == datetime.today().month)
            .filter(extract("year", Venda.data_abertura) == datetime.today().year)
            .scalar()
            or 0
        )

        # Produtos por categoria (para o gráfico)
        try:
            categorias_data = (
                db.session.query(
                    func.coalesce(CategoriaProduto.nome, "Sem categoria").label("nome"),
                    func.count(Produto.id).label("total")
                )
                .outerjoin(CategoriaProduto, CategoriaProduto.id == Produto.categoria_id)
                .group_by(CategoriaProduto.nome)
                .order_by(func.count(Produto.id).desc())
                .all()
            )
        except Exception:
            categorias_data = []

        categorias = [{"nome": nome or "Sem categoria", "total": int(total)} for nome, total in categorias_data]

        return jsonify({
            "produtos_total": total_produtos,
            "clientes_total": total_clientes,
            "documentos_validos": documentos_validos,
            "documentos_vencidos": documentos_vencidos,
            "vendas_mes": float(vendas_mes),
            "ticket_medio": float(ticket_medio),
            "categorias": categorias
        })
    except Exception as e:
        current_app.logger.error(f"Erro no dashboard_api_resumo: {e}")
        return jsonify({"error": str(e)}), 500


@main.route("/dashboard/api/timeline")
@login_required
def dashboard_api_timeline():
    """Retorna eventos recentes para a timeline."""
    try:
        eventos = []

        # Últimas vendas
        ultimas_vendas = (
            db.session.query(Venda)
            .order_by(Venda.data_abertura.desc())
            .limit(5)
            .all()
        )
        for v in ultimas_vendas:
            eventos.append({
                "tipo": "venda",
                "descricao": f"Venda #{v.id} registrada no valor de R$ {v.valor_total:.2f}",
                "data": v.data_abertura.isoformat()
            })

        # Últimos produtos cadastrados
        ultimos_produtos = (
            db.session.query(Produto)
            .order_by(Produto.criado_em.desc())
            .limit(5)
            .all()
        )
        for p in ultimos_produtos:
            eventos.append({
                "tipo": "produto",
                "descricao": f"Produto '{p.nome}' cadastrado.",
                "data": p.criado_em.isoformat() if p.criado_em else None
            })

        # Últimos clientes
        ultimos_clientes = (
            db.session.query(Cliente)
            .order_by(Cliente.id.desc())
            .limit(5)
            .all()
        )
        for c in ultimos_clientes:
            eventos.append({
                "tipo": "cliente",
                "descricao": f"Novo cliente cadastrado: {c.nome}",
                "data": datetime.today().isoformat()
            })

        # Ordena por data decrescente
        eventos.sort(key=lambda x: x["data"], reverse=True)

        return jsonify({"eventos": eventos[:10]})
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
@main.route("/configuracoes")
@login_required
def configuracoes():
    configs = Configuracao.query.all()
    return render_template("configuracoes.html", configs=configs)

@main.route("/configuracao/nova", methods=["GET", "POST"])
@main.route("/configuracao/editar/<int:config_id>", methods=["GET", "POST"])
@login_required
def gerenciar_configuracao(config_id=None):
    config = Configuracao.query.get(config_id) if config_id else None
    if request.method == "POST":
        chave, valor = request.form.get("chave"), request.form.get("valor")
        if not config:
            config = Configuracao(chave=chave, valor=valor)
            db.session.add(config)
        else:
            config.chave, config.valor = chave, valor
        db.session.commit()
        flash("Configuração salva com sucesso!", "success")
        return redirect(url_for("main.configuracoes"))
    return render_template("configuracao_form.html", config=config)

@main.route("/configuracao/excluir/<int:config_id>")
@login_required
def excluir_configuracao(config_id):
    config = Configuracao.query.get_or_404(config_id)
    db.session.delete(config)
    db.session.commit()
    flash("Configuração excluída com sucesso!", "success")
    return redirect(url_for("main.configuracoes"))

# --- Usuários ---
@main.route("/usuarios")
@login_required
def usuarios():
    users = User.query.all()
    return render_template("usuarios.html", users=users)

@main.route("/usuario/novo", methods=["GET", "POST"])
@main.route("/usuario/editar/<int:user_id>", methods=["GET", "POST"])
@login_required
def gerenciar_usuario(user_id=None):
    user = User.query.get(user_id) if user_id else None
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        if not user:
            user = User(username=username, password=password)
            db.session.add(user)
        else:
            user.username = username
            if password:
                user.password = password
        db.session.commit()
        flash("Usuário salvo com sucesso!", "success")
        return redirect(url_for("main.usuarios"))
    return render_template("usuario_form.html", user=user)

@main.route("/usuario/excluir/<int:user_id>")
@login_required
def excluir_usuario(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("main.usuarios"))

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

# --- Context Processor Global ---
@main.app_context_processor
def inject_notificacoes():
    try:
        total_nao_lidas = Notificacao.query.filter_by(status="enviado").count()
    except Exception:
        total_nao_lidas = 0
    return {"total_nao_lidas": total_nao_lidas}
