import io
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required
from .. import produtos_bp
from app.produtos.models import Produto

# ======================
# IMPORTAR PRODUTOS VIA PLANILHA
# ======================
@produtos_bp.route("/importar", methods=["GET", "POST"])
@login_required
def importar_produtos():
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if not arquivo:
            flash("Nenhum arquivo selecionado.", "warning")
            return redirect(url_for("produtos.importar_produtos"))

        try:
            from app.services.importacao import importar_produtos_planilha
            qtd, erros = importar_produtos_planilha(arquivo)
            flash(f"✅ {qtd} produtos importados com sucesso!", "success")
            if erros:
                flash(f"⚠️ Alguns produtos apresentaram erros: {', '.join(erros)}", "warning")
        except Exception as e:
            current_app.logger.error(f"Erro ao importar produtos: {e}")
            flash("❌ Erro ao processar a planilha de produtos.", "danger")

        return redirect(url_for("produtos.index"))

    return render_template("produtos/importar.html")


# ======================
# BAIXAR EXEMPLO CSV
# ======================
@produtos_bp.route("/exemplo_csv")
@login_required
def exemplo_csv():
    exemplo = io.StringIO()
    exemplo.write("codigo,nome,tipo,marca,calibre,preco_fornecedor,desconto_fornecedor,margem,ipi,ipi_tipo,difal,imposto_venda\n")
    exemplo.write("ABC123,Exemplo de Produto,Arma de Fogo,Taurus,9mm,3500,5,25,0,%_dentro,5,8\n")
    exemplo.seek(0)
    return send_file(
        io.BytesIO(exemplo.getvalue().encode("utf-8")),
        as_attachment=True,
        download_name="modelo_produtos.csv",
        mimetype="text/csv"
    )


# ======================
# API — TEXTO PARA WHATSAPP
# ======================
@produtos_bp.route("/api/produto/<int:produto_id>/whatsapp")
@login_required
def produto_whatsapp(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    if hasattr(produto, "calcular_precos"):
        produto.calcular_precos()

    texto = (
        f"*{produto.nome}*\n"
        f"💰 À vista: R$ {produto.preco_a_vista:,.2f}\n"
        f"📦 Custo total: R$ {produto.custo_total:,.2f}\n"
        f"💸 Lucro líquido: R$ {produto.lucro_liquido_real:,.2f}\n"
        f"🧮 Margem: {produto.margem or 0}%\n\n"
        f"Código: {produto.codigo}"
    )

    return jsonify({"texto_completo": texto})
