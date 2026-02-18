# ===========================================================
# ROTAS — AUTOSAVE DE PRODUTOS
# Módulo revisado — Correção Crítica de Tipos (Sprint 6I)
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

# Lista de campos que DEVEM passar pela conversão numérica
CAMPOS_DECIMAIS = [
    "preco_fornecedor", "desconto_fornecedor", "frete", "margem", 
    "ipi", "difal", "imposto_venda", "lucro_alvo", "preco_final", 
    "promo_preco_fornecedor", "custo_total", "preco_a_vista", "lucro_liquido_real"
]

# Lista de campos que são datas (para parser futuro se necessário)
CAMPOS_DATAS = ["promo_data_inicio", "promo_data_fim"]

# ===========================================================
# Função utilitária para converter valores corretamente (CORRIGIDA)
# ===========================================================
def _parse_decimal(valor):
    """
    Converte string numérica para Decimal, removendo símbolos e tratando
    o formato brasileiro (ponto como milhar, vírgula como decimal).
    Ex: "R$ 9.750,50" -> Decimal('9750.50')
    """
    if valor is None or valor == "":
        return None
    
    if isinstance(valor, (int, float, Decimal)):
        return valor

    try:
        valor_str = str(valor)
        
        # 1. Remove símbolos não numéricos (R$, %, espaços, etc.) exceto . , e -
        valor_limpo = re.sub(r'[^\d.,-]', '', valor_str)
        
        if not valor_limpo:
            return None
        
        # 2. CRÍTICO: Trata o separador de milhar (ponto) e o separador decimal (vírgula)
        # Se houver ponto E vírgula, remove o ponto (milhar) e troca a vírgula (decimal) por ponto.
        if '.' in valor_limpo and ',' in valor_limpo:
            # Ex: 1.000,00 -> 1000,00 -> 1000.00
            valor_limpo = valor_limpo.replace('.', '')
            valor_limpo = valor_limpo.replace(',', '.')
        elif ',' in valor_limpo:
            # Se só houver vírgula, troca por ponto. Ex: 100,00 -> 100.00
            valor_limpo = valor_limpo.replace(',', '.')
        # Se só houver ponto (ou nenhum), Decimal(valor_limpo) funciona. Ex: 100.00 (US) ou 1000 (sem separador).

        return Decimal(valor_limpo)
    except (InvalidOperation, ValueError):
        # Em caso de falha na conversão final, retorna None para não quebrar a transação.
        return None

@produtos_bp.route("/autosave/<int:produto_id>", methods=["POST"])
@login_required
def autosave_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    data = request.get_json() or {}
    alteracoes = {}

    CAMPOS_BOOLEANOS = ["promo_ativada", "visivel_loja", "destaque_home", "eh_lancamento", "eh_outdoor", "requer_documentacao"]

    for campo, valor_novo in data.items():
        if not hasattr(produto, campo):
            continue

        valor_atual = getattr(produto, campo)
        valor_final = valor_novo

        if campo in CAMPOS_DECIMAIS:
            valor_final = _parse_decimal(valor_novo)
        elif campo in CAMPOS_BOOLEANOS:
            valor_final = str(valor_novo).lower() in ['true', 'on', '1']
        elif campo == "meta_description":
            # Proteção contra erro de tamanho do PostgreSQL
            valor_final = str(valor_novo)[:160] if valor_novo else None
        elif campo == "nome_comercial":
            # Sincroniza o SEO simultaneamente
            produto.meta_title = valor_novo
            valor_final = valor_novo
        elif campo in CAMPOS_DATAS:
            valor_final = None if not valor_novo else valor_novo
        else:
            if isinstance(valor_novo, str):
                valor_final = valor_novo.strip()
                if valor_final == "": valor_final = None

        if campo in ["nome", "codigo"] and not valor_final:
            continue

        if str(valor_atual) != str(valor_final):
            alteracoes[campo] = {"antigo": valor_atual, "novo": valor_final}
            setattr(produto, campo, valor_final)

    if not alteracoes:
        return jsonify({"status": "no_changes"}), 200

    if hasattr(produto, 'calcular_precos'):
        produto.calcular_precos()

    produto.atualizado_em = datetime.utcnow()
    registrar_historico(produto, current_user, "autosave", alteracoes)

    try:
        db.session.commit()
        return jsonify({"status": "success", "atualizado_em": produto.atualizado_em.strftime('%H:%M')}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# ===========================================================
# ROTA — Autosave em lote (Mantido estrutura, aplicado fix)
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
            continue

        alteracoes = {}
        for campo, valor_novo in item.items():
            if campo == "id" or not hasattr(produto, campo):
                continue

            # Aplica mesma lógica segura
            if campo in CAMPOS_DECIMAIS:
                valor_final = _parse_decimal(valor_novo)
            elif campo == "promo_ativada":
                valor_final = str(valor_novo).lower() in ['true', 'on', '1']
            else:
                valor_final = valor_novo
                if isinstance(valor_final, str):
                    valor_final = valor_final.strip() or None

            # Proteção
            if campo in ["nome", "codigo"] and not valor_final:
                continue

            valor_atual = getattr(produto, campo)
            if str(valor_atual) != str(valor_final):
                alteracoes[campo] = {"antigo": valor_atual, "novo": valor_final}
                setattr(produto, campo, valor_final)

        if alteracoes:
            if hasattr(produto, 'calcular_precos'):
                produto.calcular_precos()
            produto.atualizado_em = datetime.utcnow()
            registrar_historico(produto, current_user, "autosave", alteracoes)
            resultados.append(produto.id)

    db.session.commit()
    return jsonify({"status": "success", "ids": resultados}), 200

@produtos_bp.route("/autosave/ping", methods=["GET"])
@login_required
def autosave_ping():
    return jsonify({"status": "ok"}), 200