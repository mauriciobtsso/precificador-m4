from flask import render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import login_user, logout_user, login_required
from app import db
from app.models import Produto, Taxa, User, Configuracao
from app.main import main
import os
import pandas as pd

# =========================
# Helpers
# =========================
def get_config(chave, default=None):
    """Busca configuração no banco, retorna default se não existir"""
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

def montar_parcelas(valor_base, taxas, modo="coeficiente_total"):
    """
    Gera opções de parcelamento a partir das taxas cadastradas.
    - modo="coeficiente_total": interpreta juros como acréscimo total (%) do plano
    - modo="juros_mensal": interpreta 'juros' como taxa mensal (Price).
    """
    resultado = []
    base = float(valor_base or 0)

    for taxa in taxas:
        n = int(taxa.numero_parcelas or 1)
        j = max(to_float(taxa.juros), 0.0) / 100.0

        if n <= 0:
            continue

        if n == 1 and modo == "coeficiente_total":
            coef = max(1.0 - j, 1e-9)
            total = base / coef
            parcela = total
        else:
            if modo == "juros_mensal":
                if j > 0:
                    parcela = base * (j / (1 - (1 + j) ** (-n)))
                else:
                    parcela = base / n
                total = parcela * n
            else:
                coef = max(1.0 - j, 1e-9)
                total = base / coef
                parcela = total / n

        resultado.append({
            "parcelas": n,
            "parcela": parcela,
            "total": total,
            "diferenca": total - base,
            "rotulo": f"{n}x",
        })

    return resultado

def compor_whatsapp(produto=None, valor_base=0.0, linhas=None):
    """
    Monta o texto do WhatsApp usando as configurações do sistema.
    """
    base = float(valor_base or 0)
    linhas = linhas or []

    incluir_pix = get_config("whatsapp_incluir_pix", "1") == "1"
    debito_percent = to_float(get_config("whatsapp_debito_percent", "1.09"), 1.09)
    prefixo = get_config("whatsapp_prefixo", "")

    cab = []
    if prefixo:
        cab.append(prefixo)

    if produto:
        cab.append(f"📦 Produto: {produto.nome}")
        cab.append(f"🔖 SKU: {produto.sku}")
        cab.append(f"💰 À vista: {br_money(base)}")
    else:
        cab.append("💳 Simulação de Parcelamento")
        cab.append(f"💰 À vista: {br_money(base)}")

    corpo = []

    if incluir_pix:
        corpo.append(f"PIX {br_money(base)} = {br_money(base)}")

    if debito_percent > 0:
        j = debito_percent / 100.0
        coef = max(1.0 - j, 1e-9)
        total_debito = base / coef
        corpo.append(f"Débito {br_money(total_debito)} = {br_money(total_debito)}")
    else:
        corpo.append(f"Débito {br_money(base)} = {br_money(base)}")

    for r in linhas:
        corpo.append(f"{r['rotulo']} {br_money(r['parcela'])} = {br_money(r['total'])}")

    txt = "\n".join(cab) + "\n\n" + "💳 Opções de Parcelamento:\n" + "\n".join(corpo)
    return txt

# =========================
# Função auxiliar para importação
# =========================
def to_number(x):
    """
    Converte valores para float tratando formatos de CSV/XLSX (pt-BR e en-US).
    """
    try:
        import numpy as np
        if isinstance(x, (int, float, np.number)):
            return float(x)
    except ImportError:
        if isinstance(x, (int, float)):
            return float(x)

    if x is None:
        return 0.0

    s = str(x).strip()
    if not s:
        return 0.0

    s = s.replace("R$", "").replace(" ", "")

    # Caso com ponto e vírgula → assume "." como milhar e "," como decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    # se só tiver ponto, mantém (decimal estilo en-US)

    try:
        return float(s)
    except:
        return 0.0

# =========================
# Rotas
# =========================
@main.route("/")
def index():
    return redirect(url_for("main.dashboard"))

# --- Login/Logout ---
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("main.dashboard"))
        else:
            flash("Usuário ou senha inválidos", "danger")
    return render_template("login.html")

@main.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.login"))

# --- Dashboard ---
@main.route("/dashboard")
@login_required
def dashboard():
    produtos = Produto.query.all()
    return render_template("dashboard.html", produtos=produtos)

# --- Produtos ---
@main.route("/produtos")
@login_required
def produtos():
    termo = request.args.get("termo", "").strip()
    lucro = request.args.get("lucro")
    preco_min = request.args.get("preco_min")
    preco_max = request.args.get("preco_max")

    query = Produto.query

    # filtro por nome ou SKU
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            (Produto.nome.ilike(like)) | (Produto.sku.ilike(like))
        )

    # filtro por lucro
    if lucro == "positivo":
        query = query.filter(Produto.lucro_liquido_real >= 0)
    elif lucro == "negativo":
        query = query.filter(Produto.lucro_liquido_real < 0)

    # filtro por preço
    if preco_min:
        try:
            query = query.filter(Produto.preco_a_vista >= float(preco_min))
        except:
            pass
    if preco_max:
        try:
            query = query.filter(Produto.preco_a_vista <= float(preco_max))
        except:
            pass

    produtos = query.all()
    return render_template("produtos.html", produtos=produtos)

@main.route("/produto/novo", methods=["GET", "POST"])
@main.route("/produto/editar/<int:produto_id>", methods=["GET", "POST"])
@login_required
def gerenciar_produto(produto_id=None):
    produto = Produto.query.get(produto_id) if produto_id else None
    if request.method == "POST":
        if not produto:
            produto = Produto()
            db.session.add(produto)

        produto.sku = request.form.get("sku", "").upper()
        produto.nome = request.form["nome"]

        produto.preco_fornecedor = to_float(request.form.get("preco_fornecedor"))
        produto.desconto_fornecedor = to_float(request.form.get("desconto_fornecedor"))

        produto.margem = to_float(request.form.get("margem"))
        produto.lucro_alvo = (to_float(request.form.get("lucro_alvo")) or None)
        produto.preco_final = (to_float(request.form.get("preco_final")) or None)

        produto.ipi = to_float(request.form.get("ipi"))
        produto.ipi_tipo = request.form.get("ipi_tipo", "%")
        produto.difal = to_float(request.form.get("difal"))
        produto.imposto_venda = to_float(request.form.get("imposto_venda"))

        produto.calcular_precos()
        db.session.commit()
        flash("Produto salvo com sucesso!", "success")
        return redirect(url_for("main.produtos"))

    return render_template("produto_form.html", produto=produto)

@main.route("/produto/excluir/<int:produto_id>")
@login_required
def excluir_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    db.session.delete(produto)
    db.session.commit()
    flash("Produto excluído com sucesso!", "success")
    return redirect(url_for("main.produtos"))

# --- Importação de Produtos ---
@main.route("/produtos/importar", methods=["GET", "POST"])
@login_required
def importar_produtos():
    if request.method == "POST":
        file = request.files.get("arquivo")
        if not file:
            flash("Nenhum arquivo selecionado.", "warning")
            return redirect(url_for("main.importar_produtos"))

        try:
            filename = file.filename.lower()

            # Detecta e abre o arquivo corretamente
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file, sheet_name=0)
            elif filename.endswith(".csv"):
                try:
                    df = pd.read_csv(file, encoding="utf-8-sig", sep=None, engine="python")
                except Exception:
                    file.stream.seek(0)
                    df = pd.read_csv(file, encoding="latin1", sep=None, engine="python")
            else:
                flash("Formato de arquivo não suportado. Use .csv ou .xlsx", "danger")
                return redirect(url_for("main.importar_produtos"))

            criados, atualizados = 0, 0

            for _, row in df.iterrows():
                sku = (str(row.get("sku") or "").strip().upper())
                if not sku:
                    continue

                produto = Produto.query.filter_by(sku=sku).first()
                if not produto:
                    produto = Produto(sku=sku)
                    db.session.add(produto)
                    criados += 1
                else:
                    atualizados += 1

                produto.nome = row.get("nome", produto.nome)
                produto.preco_fornecedor = to_number(row.get("preco_fornecedor"))
                produto.desconto_fornecedor = to_number(row.get("desconto_fornecedor"))
                produto.margem = to_number(row.get("margem"))
                produto.lucro_alvo = to_number(row.get("lucro_alvo")) or None
                produto.preco_final = to_number(row.get("preco_final")) or None

                produto.ipi = to_number(row.get("ipi"))
                produto.ipi_tipo = row.get("ipi_tipo") or "%"
                produto.difal = to_number(row.get("difal"))
                produto.imposto_venda = to_number(row.get("imposto_venda"))

                produto.calcular_precos()

            db.session.commit()
            flash(f"Importação concluída! {criados} criados, {atualizados} atualizados.", "success")
        except Exception as e:
            flash(f"Erro ao importar: {e}", "danger")

        return redirect(url_for("main.produtos"))

    return render_template("produtos_importar.html")

@main.route("/produtos/exemplo-csv")
@login_required
def exemplo_csv():
    pasta = os.path.join(os.path.dirname(__file__), "..", "static")
    return send_from_directory(pasta, "exemplo_produtos.csv", as_attachment=True)

# --- Taxas ---
@main.route("/taxas")
@login_required
def taxas():
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    return render_template("taxas.html", taxas=taxas)

@main.route("/taxa/nova", methods=["GET", "POST"])
@main.route("/taxa/editar/<int:taxa_id>", methods=["GET", "POST"])
@login_required
def gerenciar_taxa(taxa_id=None):
    taxa = Taxa.query.get(taxa_id) if taxa_id else None
    if request.method == "POST":
        if not taxa:
            taxa = Taxa()
            db.session.add(taxa)

        numero_parcelas_raw = request.form.get("numero_parcelas")
        juros_raw = request.form.get("juros")

        taxa.numero_parcelas = int(numero_parcelas_raw or (taxa.numero_parcelas or 1))
        taxa.juros = to_float(juros_raw, default=(taxa.juros or 0))

        db.session.commit()
        flash("Taxa salva com sucesso!", "success")
        return redirect(url_for("main.taxas"))

    return render_template("taxa_form.html", taxa=taxa)

@main.route("/taxa/excluir/<int:taxa_id>")
@login_required
def excluir_taxa(taxa_id):
    taxa = Taxa.query.get_or_404(taxa_id)
    db.session.delete(taxa)
    db.session.commit()
    flash("Taxa excluída com sucesso!", "success")
    return redirect(url_for("main.taxas"))

# --- Parcelamento ---
@main.route("/parcelamento")
@login_required
def parcelamento_index():
    produtos = Produto.query.order_by(Produto.nome).all()
    return render_template("parcelamento_index.html", produtos=produtos)

@main.route("/parcelamento/<int:produto_id>")
@login_required
def parcelamento(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()

    valor_base = produto.preco_final or produto.preco_a_vista or 0.0
    taxas_planos = [t for t in taxas if (t.numero_parcelas or 0) >= 1]
    resultado = montar_parcelas(valor_base, taxas_planos, modo="coeficiente_total")

    texto_whats = compor_whatsapp(produto=produto, valor_base=valor_base, linhas=resultado)

    return render_template("parcelamento.html", produto=produto, resultado=resultado, texto_whats=texto_whats)

@main.route("/parcelamento/rapido", methods=["GET", "POST"])
@login_required
def parcelamento_rapido():
    resultado = []
    preco_base = None
    texto_whats = ""

    if request.method == "POST":
        preco_base = to_float(request.form.get("preco_base"))
        taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
        taxas_planos = [t for t in taxas if (t.numero_parcelas or 0) >= 1]
        resultado = montar_parcelas(preco_base, taxas_planos, modo="coeficiente_total")
        texto_whats = compor_whatsapp(produto=None, valor_base=preco_base, linhas=resultado)

    return render_template("parcelamento_rapido.html", resultado=resultado, preco_base=preco_base, texto_whats=texto_whats)

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
        chave = request.form.get("chave")
        valor = request.form.get("valor")

        if not config:
            config = Configuracao(chave=chave, valor=valor)
            db.session.add(config)
        else:
            config.chave = chave
            config.valor = valor

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
        username = request.form.get("username")
        password = request.form.get("password")

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
