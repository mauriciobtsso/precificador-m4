from flask import render_template, jsonify, request
from app.produtos.precificacao import precificacao_bp
from app.services.precificacao_service import calcular_precificacao

@precificacao_bp.route("/")
def view():
    return render_template("precificacao.html")

@precificacao_bp.route("/api/precificar", methods=["POST"])
def api():
    data = request.get_json()
    resultado = calcular_precificacao(**data)
    return jsonify(resultado)
