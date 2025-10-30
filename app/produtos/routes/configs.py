# ============================================================
# MÓDULO: produtos/routes/configs.py
# Integrações de categorias, marcas, calibres, tipos e funcionamento
# ============================================================

from flask import jsonify
from flask_login import login_required
from app.produtos import produtos_bp

@produtos_bp.route("/teste_configs", methods=["GET"])
@login_required
def teste_configs():
    """Rota de teste — módulo de configs carregado."""
    return jsonify(success=True, message="Módulo 'configs' ativo ✅")
