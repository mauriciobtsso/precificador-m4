from flask import render_template, request, redirect, url_for, flash, send_from_directory, current_app, send_file
from flask_login import login_user, logout_user, login_required
from app import db
from app.models import Produto, Taxa, User, Configuracao, Cliente, Venda, ItemVenda, PedidoCompra, ItemPedido
from app.main import main
from sqlalchemy import text, func, extract
from openpyxl import load_workbook
from io import TextIOWrapper
import csv
import os
from datetime import datetime, timedelta
from app.utils.gerar_pedidos import gerar_pedido_m4

# =====================================================
# Helpers
# =====================================================
def get_config(chave, default=None):
    conf = Configuracao.query.filter_by(chave=chave).first()
    return conf.valor if conf else default

def to_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default

def br_money(v: float) -> str:
    s = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def to_number(x):
    if isinstance(x, (int, float)):
        return float(x)
    if x is None:
        return 0.0
    s = str(x).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def parse_brl(s) -> float:
    """Converte string monetária BR (R$ 1.234,56) em float"""
    if s is None:
        return 0.0
    s = str(s).strip()
    if not s:
        return 0.0
    s = s.replace('R$', '').replace('r$', '').strip()
    s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_pct(s) -> float:
    """Converte string percentual (5,5 ou 5%) em float"""
    if s is None:
        return 0.0
    s = str(s).strip().replace('%', '').replace(',', '.')
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0
# =====================================================
# Dashboard
# =====================================================
@main.route("/")
@login_required
def index():
    return redirect(url_for("main.dashboard"))

@main.route("/dashboard")
@login_required
def dashboard():
    total_produtos = Produto.query.count()
    total_clientes = Cliente.query.count()
    total_vendas = Venda.query.count()
    total_taxas = Taxa.query.count()

    return render_template(
        "dashboard.html",
        total_produtos=total_produtos,
        total_clientes=total_clientes,
        total_vendas=total_vendas,
        total_taxas=total_taxas,
    )

# =====================================================
# Produtos
# =====================================================
@main.route("/produtos")
@login_required
def listar_produtos():
    produtos = Produto.query.all()
    return render_template("produtos/listar.html", produtos=produtos)

@main.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def novo_produto():
    if request.method == "POST":
        nome = request.form.get("nome")
        preco_custo = parse_brl(request.form.get("preco_custo"))
        preco_venda = parse_brl(request.form.get("preco_venda"))
        margem = parse_pct(request.form.get("margem"))

        produto = Produto(
            nome=nome,
            preco_custo=preco_custo,
            preco_venda=preco_venda,
            margem=margem,
        )
        db.session.add(produto)
        db.session.commit()
        flash("Produto cadastrado com sucesso!", "success")
        return redirect(url_for("main.listar_produtos"))

    return render_template("produtos/novo.html")

@main.route("/produtos/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_produto(id):
    produto = Produto.query.get_or_404(id)

    if request.method == "POST":
        produto.nome = request.form.get("nome")
        produto.preco_custo = parse_brl(request.form.get("preco_custo"))
        produto.preco_venda = parse_brl(request.form.get("preco_venda"))
        produto.margem = parse_pct(request.form.get("margem"))

        db.session.commit()
        flash("Produto atualizado com sucesso!", "success")
        return redirect(url_for("main.listar_produtos"))

    return render_template("produtos/editar.html", produto=produto)

@main.route("/produtos/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    flash("Produto excluído com sucesso!", "success")
    return redirect(url_for("main.listar_produtos"))
# =====================================================
# Taxas
# =====================================================
@main.route("/taxas")
@login_required
def listar_taxas():
    taxas = Taxa.query.all()
    return render_template("taxas/listar.html", taxas=taxas)

@main.route("/taxas/novo", methods=["GET", "POST"])
@login_required
def nova_taxa():
    if request.method == "POST":
        nome = request.form.get("nome")
        percentual = parse_pct(request.form.get("percentual"))

        taxa = Taxa(nome=nome, percentual=percentual)
        db.session.add(taxa)
        db.session.commit()
        flash("Taxa cadastrada com sucesso!", "success")
        return redirect(url_for("main.listar_taxas"))

    return render_template("taxas/novo.html")

@main.route("/taxas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_taxa(id):
    taxa = Taxa.query.get_or_404(id)

    if request.method == "POST":
        taxa.nome = request.form.get("nome")
        taxa.percentual = parse_pct(request.form.get("percentual"))
        db.session.commit()
        flash("Taxa atualizada com sucesso!", "success")
        return redirect(url_for("main.listar_taxas"))

    return render_template("taxas/editar.html", taxa=taxa)

@main.route("/taxas/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_taxa(id):
    taxa = Taxa.query.get_or_404(id)
    db.session.delete(taxa)
    db.session.commit()
    flash("Taxa excluída com sucesso!", "success")
    return redirect(url_for("main.listar_taxas"))
# =====================================================
# Clientes
# =====================================================
@main.route("/clientes")
@login_required
def listar_clientes():
    clientes = Cliente.query.all()
    return render_template("clientes/listar.html", clientes=clientes)

@main.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def novo_cliente():
    if request.method == "POST":
        nome = request.form.get("nome")
        documento = request.form.get("documento")  # CPF ou CNPJ
        endereco = request.form.get("endereco")
        telefone = request.form.get("telefone")
        email = request.form.get("email")

        cliente = Cliente(
            nome=nome,
            documento=documento,
            endereco=endereco,
            telefone=telefone,
            email=email,
        )
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for("main.listar_clientes"))

    return render_template("clientes/novo.html")

@main.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nome = request.form.get("nome")
        cliente.documento = request.form.get("documento")
        cliente.endereco = request.form.get("endereco")
        cliente.telefone = request.form.get("telefone")
        cliente.email = request.form.get("email")

        db.session.commit()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("main.listar_clientes"))

    return render_template("clientes/editar.html", cliente=cliente)

@main.route("/clientes/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for("main.listar_clientes"))
# =====================================================
# Vendas
# =====================================================
@main.route("/vendas")
@login_required
def listar_vendas():
    vendas = Venda.query.all()
    return render_template("vendas/listar.html", vendas=vendas)

@main.route("/vendas/nova", methods=["GET", "POST"])
@login_required
def nova_venda():
    if request.method == "POST":
        cliente_id = request.form.get("cliente")
        data_venda = datetime.now().date()

        venda = Venda(cliente_id=cliente_id, data_venda=data_venda)
        db.session.add(venda)
        db.session.flush()  # garante venda.id

        codigos = request.form.getlist("codigo[]")
        descricoes = request.form.getlist("descricao[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        for codigo, desc, qtd, val in zip(codigos, descricoes, quantidades, valores):
            if not desc.strip():
                continue
            item = ItemVenda(
                venda_id=venda.id,
                codigo=codigo,
                descricao=desc,
                quantidade=int(qtd or 0),
                valor_unitario=parse_brl(val),
            )
            db.session.add(item)

        db.session.commit()
        flash("Venda registrada com sucesso!", "success")
        return redirect(url_for("main.listar_vendas"))

    clientes = Cliente.query.all()
    return render_template("vendas/nova.html", clientes=clientes)

@main.route("/vendas/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_venda(id):
    venda = Venda.query.get_or_404(id)
    db.session.delete(venda)
    db.session.commit()
    flash("Venda excluída com sucesso!", "success")
    return redirect(url_for("main.listar_vendas"))
# =====================================================
# Pedidos de Compra
# =====================================================
@main.route("/pedidos")
@login_required
def listar_pedidos():
    pedidos = PedidoCompra.query.order_by(PedidoCompra.data_pedido.desc()).all()
    return render_template("pedidos/listar.html", pedidos=pedidos)

@main.route("/pedidos/novo", methods=["GET", "POST"])
@login_required
def novo_pedido():
    if request.method == "POST":
        fornecedor_id = request.form.get("fornecedor")
        cond_pagto = request.form.get("cond_pagto")
        modo = request.form.get("modo_desconto")
        perc_armas = parse_pct(request.form.get("percentual_armas"))
        perc_municoes = parse_pct(request.form.get("percentual_municoes"))
        perc_unico = parse_pct(request.form.get("percentual_unico"))

        numero = datetime.now().strftime("%Y%m%d%H%M%S")

        pedido = PedidoCompra(
            numero=numero,
            data_pedido=datetime.now().date(),
            cond_pagto=cond_pagto,
            modo_desconto=modo,
            percentual_armas=perc_armas,
            percentual_municoes=perc_municoes,
            percentual_unico=perc_unico,
            fornecedor_id=fornecedor_id,
        )
        db.session.add(pedido)
        db.session.flush()

        codigos = request.form.getlist("codigo[]")
        descricoes = request.form.getlist("descricao[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        for codigo, desc, qtd, val in zip(codigos, descricoes, quantidades, valores):
            if not desc.strip():
                continue
            item = ItemPedido(
                pedido_id=pedido.id,
                codigo=codigo,
                descricao=desc,
                quantidade=int(qtd or 0),
                valor_unitario=parse_brl(val),
            )
            db.session.add(item)

        db.session.commit()
        flash("Pedido criado com sucesso!", "success")
        return redirect(url_for("main.listar_pedidos"))

    # Apenas fornecedores com CNPJ válido
    fornecedores = [
        c for c in Cliente.query.all()
        if c.documento and len(c.documento) == 18 and "/" in c.documento
    ]
    return render_template("pedidos/novo.html", fornecedores=fornecedores)

@main.route("/pedidos/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)

    if request.method == "POST":
        pedido.cond_pagto = request.form.get("cond_pagto")
        pedido.modo_desconto = request.form.get("modo_desconto")
        pedido.percentual_armas = parse_pct(request.form.get("percentual_armas"))
        pedido.percentual_municoes = parse_pct(request.form.get("percentual_municoes"))
        pedido.percentual_unico = parse_pct(request.form.get("percentual_unico"))

        # Remove itens antigos e recria
        ItemPedido.query.filter_by(pedido_id=pedido.id).delete()

        codigos = request.form.getlist("codigo[]")
        descricoes = request.form.getlist("descricao[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        for codigo, desc, qtd, val in zip(codigos, descricoes, quantidades, valores):
            if not desc.strip():
                continue
            item = ItemPedido(
                pedido_id=pedido.id,
                codigo=codigo,
                descricao=desc,
                quantidade=int(qtd or 0),
                valor_unitario=parse_brl(val),
            )
            db.session.add(item)

        db.session.commit()
        flash("Pedido atualizado com sucesso!", "success")
        return redirect(url_for("main.listar_pedidos"))

    fornecedores = [
        c for c in Cliente.query.all()
        if c.documento and len(c.documento) == 18 and "/" in c.documento
    ]
    return render_template("pedidos/editar.html", pedido=pedido, fornecedores=fornecedores)

@main.route("/pedidos/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)
    db.session.delete(pedido)
    db.session.commit()
    flash("Pedido excluído com sucesso!", "success")
    return redirect(url_for("main.listar_pedidos"))

@main.route("/pedidos/<int:id>/pdf")
@login_required
def pedido_pdf(id):
    pedido = PedidoCompra.query.get_or_404(id)
    itens = ItemPedido.query.filter_by(pedido_id=pedido.id).all()

    filename = f"pedido_{pedido.numero}.pdf"
    filepath = os.path.join(current_app.root_path, "static", "pdf", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    gerar_pedido_m4(pedido=pedido, itens=itens, output_path=filepath)

    return send_file(filepath, mimetype="application/pdf")
# =====================================================
# Configurações
# =====================================================
@main.route("/configuracoes", methods=["GET", "POST"])
@login_required
def configuracoes():
    if request.method == "POST":
        for chave, valor in request.form.items():
            conf = Configuracao.query.filter_by(chave=chave).first()
            if conf:
                conf.valor = valor
            else:
                db.session.add(Configuracao(chave=chave, valor=valor))
        db.session.commit()
        flash("Configurações salvas com sucesso!", "success")
        return redirect(url_for("main.configuracoes"))

    configuracoes = Configuracao.query.all()
    return render_template("configuracoes.html", configuracoes=configuracoes)

# =====================================================
# Usuários
# =====================================================
@main.route("/usuarios")
@login_required
def listar_usuarios():
    usuarios = User.query.all()
    return render_template("usuarios/listar.html", usuarios=usuarios)

@main.route("/usuarios/novo", methods=["GET", "POST"])
@login_required
def novo_usuario():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if User.query.filter_by(username=username).first():
            flash("Usuário já existe!", "danger")
            return redirect(url_for("main.novo_usuario"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Usuário criado com sucesso!", "success")
        return redirect(url_for("main.listar_usuarios"))

    return render_template("usuarios/novo.html")

@main.route("/usuarios/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_usuario(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("main.listar_usuarios"))
# =====================================================
# Exportações
# =====================================================
@main.route("/exportar/produtos/csv")
@login_required
def exportar_produtos_csv():
    filepath = os.path.join(current_app.root_path, "static", "export", "produtos.csv")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID", "Nome", "Preço Custo", "Preço Venda", "Margem"])
        for p in Produto.query.all():
            writer.writerow([p.id, p.nome, p.preco_custo, p.preco_venda, p.margem])

    return send_file(filepath, mimetype="text/csv", as_attachment=True)

@main.route("/exportar/clientes/csv")
@login_required
def exportar_clientes_csv():
    filepath = os.path.join(current_app.root_path, "static", "export", "clientes.csv")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID", "Nome", "Documento", "Endereço", "Telefone", "Email"])
        for c in Cliente.query.all():
            writer.writerow([c.id, c.nome, c.documento, c.endereco, c.telefone, c.email])

    return send_file(filepath, mimetype="text/csv", as_attachment=True)

@main.route("/exportar/vendas/csv")
@login_required
def exportar_vendas_csv():
    filepath = os.path.join(current_app.root_path, "static", "export", "vendas.csv")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID", "Cliente", "Data"])
        for v in Venda.query.all():
            writer.writerow([v.id, v.cliente.nome if v.cliente else "", v.data_venda])

    return send_file(filepath, mimetype="text/csv", as_attachment=True)

# =====================================================
# Arquivos Estáticos (PDF, Export, etc.)
# =====================================================
@main.route("/static/pdf/<path:filename>")
@login_required
def pdf_files(filename):
    return send_from_directory(os.path.join(current_app.root_path, "static", "pdf"), filename)

@main.route("/static/export/<path:filename>")
@login_required
def export_files(filename):
    return send_from_directory(os.path.join(current_app.root_path, "static", "export"), filename)
