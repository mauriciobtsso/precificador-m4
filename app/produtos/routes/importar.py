# ============================================================
# MÓDULO: IMPORTAÇÃO DE PRODUTOS — Sprint 6G (Revisado Final ✅)
# ============================================================

import re
import os
import csv
import math
import pandas as pd
from io import StringIO
from decimal import Decimal, InvalidOperation
from datetime import datetime
from flask import (
    render_template, request, flash, redirect, url_for,
    current_app, send_file, session, jsonify
)
from flask_login import login_required, current_user

from app import db
from app.produtos import produtos_bp
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto
)
from app.produtos.utils.historico_helper import registrar_historico


# ------------------------------------------------------------
# Config/Constantes
# ------------------------------------------------------------
COLUNAS_ESPERADAS = [
    "sku", "nome", "preco_fornecedor", "desconto_fornecedor",
    "margem", "ipi", "ipi_tipo", "difal", "imposto_venda",
    "tipo", "categoria", "marca", "calibre", "funcionamento",
]


# ------------------------------------------------------------
# Utils numéricos e limpeza
# ------------------------------------------------------------
def _to_float(valor, default=None):
    if valor is None:
        return default
    s = str(valor).strip()
    if not s or s.lower() == "nan":
        return default
    s = re.sub(r"[^\d,.\-+]", "", s)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def _to_str_or_none(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def _sanitize_ipi_tipo(valor):
    v = _to_str_or_none(valor)
    if not v:
        return "%"
    v = v.replace("R$", "R$").replace("%", "%")
    if v not in ("%", "R$"):
        return "%"
    return v


# ------------------------------------------------------------
# Helpers de leitura/preview
# ------------------------------------------------------------
def _ler_dataframe(caminho_arquivo: str, filename: str) -> pd.DataFrame:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        return pd.read_csv(
            caminho_arquivo,
            sep=None,
            engine="python",
            decimal=",",
            thousands=".",
            dtype=str,
        )
    elif ext in (".xls", ".xlsx"):
        return pd.read_excel(
            caminho_arquivo,
            dtype=str,
            decimal=",",
            thousands="."
        )
    else:
        raise ValueError("Formato não suportado. Use .csv ou .xlsx.")


def _validar_colunas(df: pd.DataFrame):
    cols = [c.strip().lower() for c in df.columns]
    faltantes = [c for c in COLUNAS_ESPERADAS[:9] if c not in cols]
    return faltantes


def _status_linhas(df: pd.DataFrame):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    skus = [str(x).strip() for x in df.get("sku", [])]
    existentes = set()
    if skus:
        existentes = {p.codigo for p in Produto.query.filter(Produto.codigo.in_(skus)).all()}

    linhas = []
    for _, row in df.iterrows():
        linha = {c: row.get(c) for c in df.columns}
        sku = _to_str_or_none(row.get("sku"))
        nome = _to_str_or_none(row.get("nome"))
        if not sku or not nome:
            linhas.append({**linha, "status": "erro", "motivo": "Falta SKU ou nome"})
            continue

        numericos = ["preco_fornecedor", "desconto_fornecedor", "margem", "ipi", "difal", "imposto_venda"]
        invalido = False
        for n in numericos:
            valor = _to_str_or_none(row.get(n))
            if not valor:
                continue
            test = _to_float(valor, default=None)
            if test is None:
                invalido = True
                break
        if invalido:
            linhas.append({**linha, "status": "erro", "motivo": "Valor numérico inválido"})
            continue

        status = "atualizar" if sku in existentes else "novo"
        linhas.append({**linha, "status": status})
    return linhas


def _montar_preview_html(linhas: list) -> str:
    cols = [
        "sku", "nome", "preco_fornecedor", "desconto_fornecedor", "margem",
        "ipi", "ipi_tipo", "difal", "imposto_venda", "tipo", "categoria",
        "marca", "calibre", "funcionamento", "status"
    ]
    thead = "<thead><tr>" + "".join(f"<th class='text-nowrap'>{c}</th>" for c in cols) + "</tr></thead>"
    rows_html = []
    for ln in linhas:
        status = ln.get("status", "")
        cls = (
            "table-success" if status == "novo" else
            "table-warning" if status == "atualizar" else
            "table-danger" if status == "erro" else ""
        )
        tds = []
        for c in cols:
            val = ln.get(c, "")
            if c == "status" and status == "erro":
                val = f"erro — {ln.get('motivo','')}"
            tds.append(f"<td class='align-middle'>{val}</td>")
        rows_html.append(f"<tr class='{cls}'>" + "".join(tds) + "</tr>")
    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    return f"<table class='table table-sm table-striped table-hover align-middle mb-0'>{thead}{tbody}</table>"


# ------------------------------------------------------------
# Helpers ORM (_get_or_create e cálculo)
# ------------------------------------------------------------
def _get_or_create(model, nome: str | None):
    n = _to_str_or_none(nome)
    if not n:
        return None
    with db.session.no_autoflush:
        obj = model.query.filter(db.func.lower(model.nome) == n.lower()).first()
        if obj:
            return obj
        obj = model(nome=n, descricao="")
        db.session.add(obj)
        return obj


def _calcular_precos(produto: Produto):
    preco_fornecedor = float(_to_float(produto.preco_fornecedor, 0.0) or 0.0)
    desconto = float(_to_float(produto.desconto_fornecedor, 0.0) or 0.0)
    margem = float(_to_float(produto.margem, 0.0) or 0.0)
    ipi = float(_to_float(produto.ipi, 0.0) or 0.0)
    ipi_tipo = _sanitize_ipi_tipo(produto.ipi_tipo)
    difal = float(_to_float(produto.difal, 0.0) or 0.0)
    imposto_venda = float(_to_float(produto.imposto_venda, 0.0) or 0.0)
    frete = float(_to_float(getattr(produto, "frete", 0.0), 0.0) or 0.0)

    preco_base = preco_fornecedor * (1.0 - desconto/100.0) + frete
    if ipi_tipo == "%":
        preco_base *= (1.0 + ipi/100.0)
    else:
        preco_base += ipi

    custo_total = preco_base * (1.0 + difal/100.0)
    preco_liquido = custo_total * (1.0 + imposto_venda/100.0)
    preco_sugerido = preco_liquido * (1.0 + margem/100.0)
    produto.custo_total = round(custo_total, 6)

    try:
        preco_final_float = float(produto.preco_final) if produto.preco_final is not None else None
    except (ValueError, InvalidOperation):
        preco_final_float = None
    if preco_final_float is not None:
        produto.lucro_liquido_real = round(preco_final_float - custo_total, 6)
    else:
        produto.lucro_liquido_real = None

    return {"custo_total": produto.custo_total, "preco_sugerido": round(preco_sugerido, 6)}


# ============================================================
# ROTA: Exemplo CSV (modelo para download)
# ============================================================
@produtos_bp.route("/exemplo_csv", methods=["GET"], endpoint="exemplo_csv")
@login_required
def exemplo_csv():
    exemplo = StringIO()
    writer = csv.writer(exemplo, delimiter=";")
    writer.writerow([
        "sku", "nome", "tipo", "categoria", "marca", "calibre", "funcionamento",
        "preco_fornecedor", "desconto_fornecedor", "margem", "ipi",
        "ipi_tipo", "difal", "imposto_venda"
    ])
    writer.writerow([
        "ABC123", "Pistola Taurus G3C", "Arma", "Pistola", "Taurus",
        "9mm", "Semiautomática", "3.500,00", "5", "20", "15", "%", "2", "6"
    ])
    exemplo.seek(0)
    pasta_export = os.path.join(current_app.instance_path, "exports")
    os.makedirs(pasta_export, exist_ok=True)
    caminho_csv = os.path.join(pasta_export, "modelo_importacao.csv")
    with open(caminho_csv, "w", encoding="utf-8") as f:
        f.write(exemplo.getvalue())
    return send_file(
        caminho_csv,
        as_attachment=True,
        download_name="modelo_importacao.csv",
        mimetype="text/csv"
    )


# ============================================================
# ROTA: Importar Produtos (Upload + Prévia)
# ============================================================
@produtos_bp.route("/importar", methods=["GET", "POST"], endpoint="importar_produtos")
@login_required
def importar_produtos():
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if not arquivo:
            flash("Nenhum arquivo selecionado.", "warning")
            return redirect(url_for("produtos.importar_produtos"))

        temp_dir = os.path.join(current_app.instance_path, "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        caminho_arquivo = os.path.join(temp_dir, arquivo.filename)
        arquivo.save(caminho_arquivo)

        try:
            df = _ler_dataframe(caminho_arquivo, arquivo.filename)
            df.columns = [c.strip().lower() for c in df.columns]
        except Exception as e:
            flash(f"Erro ao ler o arquivo: {e}", "danger")
            return redirect(url_for("produtos.importar_produtos"))

        faltantes = _validar_colunas(df)
        if faltantes:
            flash(f"Colunas ausentes: {', '.join(faltantes)}", "danger")
            return redirect(url_for("produtos.importar_produtos"))

        linhas = _status_linhas(df)
        preview_html = _montar_preview_html(linhas)
        session["importar_temp_path"] = caminho_arquivo
        session["importar_filename"] = arquivo.filename

        total = len(linhas)
        novos = sum(1 for l in linhas if l.get("status") == "novo")
        atualizar = sum(1 for l in linhas if l.get("status") == "atualizar")
        erros = sum(1 for l in linhas if l.get("status") == "erro")

        flash(f"Arquivo carregado: {total} linha(s).", "success")
        return render_template(
            "produtos/importar.html",
            preview_html=preview_html,
            total=total, novos=novos, atualizar=atualizar, erros=erros,
            pronto_confirmar=True
        )
    return render_template("produtos/importar.html")


# ============================================================
# ROTA: Confirmar Importação (Gravação no Banco + Histórico)
# ============================================================
@produtos_bp.route("/importar/confirmar", methods=["POST"], endpoint="importar_confirmar")
@login_required
def importar_confirmar():
    caminho = session.get("importar_temp_path")
    filename = session.get("importar_filename")
    if not caminho or not os.path.exists(caminho):
        flash("Arquivo temporário não encontrado. Refaça o upload.", "warning")
        return redirect(url_for("produtos.importar_produtos"))

    try:
        df = _ler_dataframe(caminho, filename)
        df.columns = [c.strip().lower() for c in df.columns]
    except Exception as e:
        flash(f"Erro ao reabrir o arquivo: {e}", "danger")
        return redirect(url_for("produtos.importar_produtos"))

    criados = atualizados = ignorados = 0

    try:
        with db.session.no_autoflush:
            for _, row in df.iterrows():
                sku = _to_str_or_none(row.get("sku"))
                nome = _to_str_or_none(row.get("nome"))
                if not sku or not nome:
                    ignorados += 1
                    continue

                produto = Produto.query.filter_by(codigo=sku).first()
                criando = produto is None

                if criando:
                    # 🔹 Cria já com nome para não violar NOT NULL no flush
                    produto = Produto(codigo=sku, nome=nome)
                    db.session.add(produto)
                    db.session.flush()  # garante o produto.id

                alteracoes = {}

                def set_campo(campo, novo_valor):
                    atual = getattr(produto, campo)
                    if str(atual) != str(novo_valor):
                        alteracoes[campo] = {"antigo": atual, "novo": novo_valor}
                        setattr(produto, campo, novo_valor)

                tipo = _get_or_create(TipoProduto, row.get("tipo"))
                categoria = _get_or_create(CategoriaProduto, row.get("categoria"))
                marca = _get_or_create(MarcaProduto, row.get("marca"))
                calibre = _get_or_create(CalibreProduto, row.get("calibre"))
                funcionamento = _get_or_create(FuncionamentoProduto, row.get("funcionamento"))

                set_campo("tipo_id", tipo.id if tipo else None)
                set_campo("categoria_id", categoria.id if categoria else None)
                set_campo("marca_id", marca.id if marca else None)
                set_campo("calibre_id", calibre.id if calibre else None)
                set_campo("funcionamento_id", funcionamento.id if funcionamento else None)

                set_campo("nome", nome)
                set_campo("preco_fornecedor", _to_float(row.get("preco_fornecedor"), 0.0))
                set_campo("desconto_fornecedor", _to_float(row.get("desconto_fornecedor"), 0.0))
                set_campo("margem", _to_float(row.get("margem"), 0.0))
                set_campo("ipi", _to_float(row.get("ipi"), 0.0))
                set_campo("ipi_tipo", _sanitize_ipi_tipo(row.get("ipi_tipo")))
                set_campo("difal", _to_float(row.get("difal"), 0.0))
                set_campo("imposto_venda", _to_float(row.get("imposto_venda"), 0.0))

                for campo_extra in ("preco_final", "preco_a_vista", "lucro_alvo"):
                    if campo_extra in row:
                        valor = _to_float(row.get(campo_extra), None)
                        if valor is not None:
                            set_campo(campo_extra, valor)

                produto.atualizado_em = datetime.utcnow()
                _calcular_precos(produto)

                if produto.id:
                    registrar_historico(produto, current_user, "importação", alteracoes)

                criados += 1 if criando else 0
                atualizados += 1 if not criando else 0

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao salvar no banco: {e}", "danger")
        current_app.logger.exception(e)
        return redirect(url_for("produtos.importar_produtos"))

    flash(f"✅ Importação concluída: {criados} criados, {atualizados} atualizados, {ignorados} ignorados.", "success")

    session["alerta_importacao"] = (
        f"🟢 Importação concluída — {criados} novos e {atualizados} atualizados "
        f"às {datetime.now().strftime('%H:%M')} por {getattr(current_user, 'nome', current_user.username)}."
    )

    try:
        db.session.execute(
            """
            INSERT INTO importacoes_log (usuario, data_hora, novos, atualizados, total)
            VALUES (:usuario, :data_hora, :novos, :atualizados, :total)
            """,
            {
                "usuario": getattr(current_user, "nome", current_user.username),
                "data_hora": datetime.utcnow(),
                "novos": criados,
                "atualizados": atualizados,
                "total": criados + atualizados,
            },
        )
        db.session.commit()
    except Exception as e:
        current_app.logger.warning(f"Falha ao registrar log de importação: {e}")

    return redirect(url_for("produtos.index"))
