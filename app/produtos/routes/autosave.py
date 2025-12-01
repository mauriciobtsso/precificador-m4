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

# ===========================================================
# ROTA — Autosave de campos individuais do produto
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
        valor_final = valor_novo

        # 1. Tratamento Específico por Tipo de Campo
        if campo in CAMPOS_DECIMAIS:
            # É dinheiro/número: usa o parser seguro (agora corrigido)
            valor_final = _parse_decimal(valor_novo)
        elif campo == "promo_ativada":
            # Checkbox: vem como boolean ou string "on"/"true"
            valor_final = str(valor_novo).lower() in ['true', 'on', '1']
        elif campo in CAMPOS_DATAS:
            # Datas: Se vier vazio, é None. 
            if not valor_novo:
                valor_final = None
        else:
            # Texto Puro (Nome, Código, Descrição): Mantém original, remove espaços extras
            if isinstance(valor_novo, str):
                valor_final = valor_novo.strip()
                if valor_final == "":
                    valor_final = None
            
        # 2. Proteção contra Nulos em Campos Obrigatórios
        if campo in ["nome", "codigo"] and not valor_final:
            # Se tentar limpar o nome ou código, ignoramos essa alteração específica
            continue

        # 3. Comparação para detectar mudança
        str_atual = str(valor_atual) if valor_atual is not None else ""
        str_novo = str(valor_final) if valor_final is not None else ""
        
        # NOTE: A comparação de strings pode ser frágil para floats/Decimals.
        # Devido ao _parse_decimal retornar None em falha, a mudança é detectada corretamente.
        if str_atual != str_novo:
            alteracoes[campo] = {"antigo": valor_atual, "novo": valor_final}
            setattr(produto, campo, valor_final)

    # Nenhuma mudança → resposta imediata
    if not alteracoes:
        return jsonify({"status": "no_changes"}), 200

    # Recalcula preços se necessário
    if hasattr(produto, 'calcular_precos'):
        produto.calcular_precos()

    # Atualiza timestamp
    produto.atualizado_em = datetime.utcnow()

    # Registra histórico
    registrar_historico(produto, current_user, "autosave", alteracoes)

    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "alteracoes": list(alteracoes.keys()),
            "produto_id": produto.id,
            "updated": True,
            "atualizado_em": produto.atualizado_em.strftime('%H:%M')
        }), 200
    except Exception as e:
        db.session.rollback()
        # Log do erro para debug mas retorno JSON amigável
        print(f"[Autosave Error] {e}") 
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