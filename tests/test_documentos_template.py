from pathlib import Path

from flask import Flask

from app.loja import loja_bp


TEMPLATE = Path(__file__).parents[1] / "app/loja/templates/loja/cliente/documentos.html"


def test_formulario_de_arma_aponta_para_rota_existente():
    conteudo = TEMPLATE.read_text(encoding="utf-8")

    assert "url_for('loja.nova_arma')" in conteudo
    assert "url_for('loja.solicitar_arma')" not in conteudo


def test_rota_nova_arma_esta_registrada_no_blueprint():
    app = Flask(__name__)
    app.register_blueprint(loja_bp)

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "loja.nova_arma" in endpoints
