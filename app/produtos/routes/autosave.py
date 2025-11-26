# ===========================================================
# ROTAS — AUTOSAVE DE PRODUTOS
# Módulo revisado — Sprint 6H (Integração com registrar_historico)
# ===========================================================

from flask import request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from app import db
from app.produtos.models import Produto
from app.produtos.utils.historico_helper import registrar_historico

# Importamos o Blueprint principal do módulo
from .. import produtos_bp 

# ===========================================================
# Função utilitária para converter valores corretamente
# ===========================================================
def _parse_valor(valor):
    """
    Converte string numérica para Decimal, removendo símbolos de moeda e porcentagem.
    Ex: "R$ 9,75" -> Decimal('9.75')
        "27,00 %" -> Decimal('27.00')
    """
    if valor is None or valor == "":
        return None
    
    # Se já for numérico, retorna direto
    if isinstance(valor, (int, float, Decimal)):
        return valor

    try:
        valor_str = str(valor)
        
        # 1. Remove tudo que NÃO for dígito, vírgula, ponto ou sinal de menos
        # Isso elimina "R$", "%", espaços, etc.
        valor_limpo = re.sub(r'[^\d.,-]', '', valor_str)
        
        if not valor_limpo:
            return None

        # 2. Substitui vírgula por ponto para formato padrão Python
        valor_limpo = valor_limpo.replace(",", ".")
        
        return Decimal(valor_limpo)

    except (InvalidOperation, ValueError):
        # Se falhar na conversão, retorna None para não quebrar o banco
        return None


# ===========================================================
# ROTA — Autosave de campos individuais do produto
# URL Final: /produtos/autosave/<id>
# ===========================================================
@produtos_bp.route("/autosave/<int:produto_id>", methods=["POST"])
@login_required
def autosave_produto(produto_id):
    """
    Recebe alterações parciais via AJAX e salva no banco em tempo real.
    """
    produto = Produto.query.get_or_404(produto_id)
    data = request.get_json() or {}

    alteracoes = {}

    for campo, valor_novo in data.items():
        # Ignora campos que não existem no modelo
        if not hasattr(produto, campo):
            continue

        valor_atual = getattr(produto, campo)
        
        # Aplica a conversão segura
        valor_convertido = _parse_valor(valor_novo)

        # Evita falsos positivos de comparação (string vs decimal)
        # Compara as strings dos valores para ver se mudou
        str_atual = str(valor_atual) if valor_atual is not None else ""
        str_novo = str(valor_convertido) if valor_convertido is not None else ""
        
        # Pequeno ajuste para tratar '10.00' igual a '10' se necessário, 
        # mas para monetário a comparação de string costuma bastar se normalizada.
        if str_atual != str_novo:
            # Guarda o valor antigo para o histórico
            alteracoes[campo] = {"antigo": valor_atual, "novo": valor_convertido}
            
            # Atualiza o objeto
            setattr(produto, campo, valor_convertido)

    # Nenhuma mudança → resposta imediata
    if not alteracoes:
        return jsonify({"status": "no_changes"}), 200

    # Recalcula preços se necessário (margem, lucro, etc)
    # Isso garante que se eu mudar o custo, o preço final atualize (se houver lógica para tal)
    if hasattr(produto, 'calcular_precos'):
        produto.calcular_precos()

    # Atualiza timestamp
    produto.atualizado_em = datetime.utcnow()

    # Registra histórico
    registrar_historico(produto, current_user, "autosave", alteracoes)

    db.session.commit()

    return jsonify({
        "status": "success",
        "alteracoes": list(alteracoes.keys()),
        "produto_id": produto.id,
        "usuario": getattr(current_user, "nome", None) or current_user.username,
    }), 200


# ===========================================================
# ROTA — Autosave em lote
# URL Final: /produtos/autosave/lote
# ===========================================================
@produtos_bp.route("/autosave/lote", methods=["POST"])
@login_required
def autosave_lote():
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
            
            str_atual = str(valor_atual) if valor_atual is not None else ""
            str_novo = str(valor_convertido) if valor_convertido is not None else ""

            if str_atual != str_novo:
                alteracoes[campo] = {"antigo": valor_atual, "novo": valor_convertido}
                setattr(produto, campo, valor_convertido)

        if alteracoes:
            if hasattr(produto, 'calcular_precos'):
                produto.calcular_precos()
            produto.atualizado_em = datetime.utcnow()
            registrar_historico(produto, current_user, "autosave", alteracoes)
            resultados.append({"id": produto.id, "status": "updated", "campos": list(alteracoes.keys())})
        else:
            resultados.append({"id": produto.id, "status": "no_changes"})

    db.session.commit()
    return jsonify({"status": "success", "resultados": resultados}), 200


# ===========================================================
# ROTA — Diagnóstico
# URL Final: /produtos/autosave/ping
# ===========================================================
@produtos_bp.route("/autosave/ping", methods=["GET"])
@login_required
def autosave_ping():
    return jsonify({
        "status": "ok",
        "mensagem": "Autosave ativo.",
        "usuario": getattr(current_user, "nome", None) or current_user.username,
    }), 200