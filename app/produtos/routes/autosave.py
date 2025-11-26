# ===========================================================
# ROTAS — AUTOSAVE DE PRODUTOS
# Módulo revisado — Sprint 6H (Integração com registrar_historico)
# ===========================================================

from flask import request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app import db
from app.produtos.models import Produto, ProdutoHistorico
from app.produtos.utils.historico_helper import registrar_historico

# CORREÇÃO: Importamos o Blueprint principal do módulo em vez de criar um novo
from .. import produtos_bp 

# ===========================================================
# Função utilitária para converter valores corretamente
# ===========================================================
def _parse_valor(valor):
    """Converte string numérica para Decimal, se aplicável."""
    if valor is None or valor == "":
        return None
    try:
        valor_str = str(valor).replace(",", ".")
        return Decimal(valor_str)
    except (InvalidOperation, ValueError):
        return valor


# ===========================================================
# ROTA — Autosave de campos individuais do produto
# URL Final: /produtos/autosave/<id> (Prefixo /produtos vem do Blueprint)
# ===========================================================
@produtos_bp.route("/autosave/<int:produto_id>", methods=["POST"])
@login_required
def autosave_produto(produto_id):
    """
    Recebe alterações parciais via AJAX e salva no banco em tempo real.
    Cria registros de histórico apenas para os campos realmente alterados.
    """
    produto = Produto.query.get_or_404(produto_id)
    data = request.get_json() or {}

    alteracoes = {}

    for campo, valor_novo in data.items():
        if not hasattr(produto, campo):
            continue

        valor_atual = getattr(produto, campo)
        valor_convertido = _parse_valor(valor_novo)

        # Evita falsos positivos de comparação
        if str(valor_atual) != str(valor_convertido):
            alteracoes[campo] = {"antigo": valor_atual, "novo": valor_convertido}
            setattr(produto, campo, valor_convertido)

    # Nenhuma mudança → resposta imediata
    if not alteracoes:
        return jsonify({"status": "no_changes"}), 200

    # Atualiza timestamp de modificação
    produto.atualizado_em = datetime.utcnow()

    # Cria registros de histórico centralizados
    registrar_historico(produto, current_user, "autosave", alteracoes)

    db.session.commit()

    return jsonify({
        "status": "success",
        "alteracoes": list(alteracoes.keys()),
        "produto_id": produto.id,
        "usuario": getattr(current_user, "nome", None) or current_user.username,
    }), 200


# ===========================================================
# ROTA — Autosave em lote (vários produtos)
# URL Final: /produtos/autosave/lote
# ===========================================================
@produtos_bp.route("/autosave/lote", methods=["POST"])
@login_required
def autosave_lote():
    """
    Permite salvar múltiplos produtos em lote.
    """
    payload = request.get_json() or {}
    produtos_data = payload.get("produtos", [])
    resultados = []

    for item in produtos_data:
        produto_id = item.get("id")
        produto = Produto.query.get(produto_id)
        if not produto:
            resultados.append({"id": produto_id, "status": "not_found"})
            continue

        alteracoes = {}
        for campo, valor_novo in item.items():
            if campo == "id" or not hasattr(produto, campo):
                continue

            valor_atual = getattr(produto, campo)
            valor_convertido = _parse_valor(valor_novo)

            if str(valor_atual) != str(valor_convertido):
                alteracoes[campo] = {"antigo": valor_atual, "novo": valor_convertido}
                setattr(produto, campo, valor_convertido)

        if alteracoes:
            produto.atualizado_em = datetime.utcnow()
            registrar_historico(produto, current_user, "autosave", alteracoes)
            resultados.append({"id": produto.id, "status": "updated", "campos": list(alteracoes.keys())})
        else:
            resultados.append({"id": produto.id, "status": "no_changes"})

    db.session.commit()
    return jsonify({"status": "success", "resultados": resultados}), 200


# ===========================================================
# ROTA — Diagnóstico rápido de autosave
# URL Final: /produtos/autosave/ping
# ===========================================================
@produtos_bp.route("/autosave/ping", methods=["GET"])
@login_required
def autosave_ping():
    """Usado apenas para testar se o módulo está ativo."""
    return jsonify({
        "status": "ok",
        "mensagem": "Autosave ativo e integrado ao histórico.",
        "usuario": getattr(current_user, "nome", None) or current_user.username,
    }), 200