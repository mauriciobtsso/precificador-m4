# ======================
# ALERTAS - ROTAS
# ======================

from flask import render_template, request, jsonify
from app.alertas import alertas_bp
from app.utils.alertas import gerar_alertas_gerais


# ----------------------
# Rota: /alertas (HTML)
# ----------------------
@alertas_bp.route("/alertas")
def listar_alertas():
    """
    Exibe a página principal do módulo de alertas detalhados.
    Nesta rota é carregado o template HTML, e os dados são
    obtidos via chamada assíncrona à rota /api/alertas.
    """
    return render_template("alertas.html", titulo="Módulo de Alertas")


# ----------------------
# Rota: /api/alertas (JSON)
# ----------------------
@alertas_bp.route("/api/alertas")
def api_alertas():
    """
    Endpoint paginado de alertas com filtros dinâmicos.
    Consome a função gerar_alertas_gerais() do módulo utils/alertas.py
    para consolidar dados reais (documentos, armas, CR, processos).
    """

    # 🔹 Parâmetros de consulta (query params)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    tipo = request.args.get("tipo", "").strip()
    nivel = request.args.get("nivel", "").strip()
    q = request.args.get("q", "").strip()
    inicio = request.args.get("inicio", "").strip()
    fim = request.args.get("fim", "").strip()

    # 🔹 Monta dicionário de filtros
    filtros = {
        "tipo": tipo or None,
        "nivel": nivel or None,
        "q": q or None,
        "inicio": inicio or None,
        "fim": fim or None,
    }

    # 🔹 Gera alertas consolidados
    resultado = gerar_alertas_gerais(filtros=filtros, page=page, per_page=per_page)

    # 🔹 Retorna resposta JSON padronizada
    return jsonify(resultado)
