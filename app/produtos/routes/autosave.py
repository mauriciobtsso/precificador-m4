from flask import request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from . import produtos_bp
from app.produtos.models import Produto, ProdutoHistorico

# ======================================================
# AUTO-SAVE - Atualiza produto parcialmente via AJAX + Histórico
# ======================================================
@produtos_bp.route("/autosave/<int:produto_id>", methods=["POST"])
@login_required
def autosave_produto(produto_id):
    """Salvamento automático de campos alterados (AJAX) + registro de histórico."""
    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({"success": False, "error": "Produto não encontrado"}), 404

    # Recebe JSON do frontend
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"success": False, "error": "Nenhum dado recebido"}), 400

    alteracoes = []
    campos_atualizados = []

    try:
        for field, value in data.items():
            if not hasattr(produto, field):
                continue

            valor_atual = getattr(produto, field)
            # Limpeza e conversão de valores
            if value in ["", None]:
                novo_valor = None
            else:
                val_str = str(value).strip()

                # Remove R$, %, espaços e converte corretamente formatos brasileiros para float
                if any(s in val_str for s in ["R$", "%", ",", "."]):
                    # Remove símbolos e espaços, mas mantém separadores
                    val_str = val_str.replace("R$", "").replace("%", "").strip()

                    # Se tiver vírgula e ponto, assume que o ponto é milhar e vírgula é decimal
                    if "," in val_str and "." in val_str:
                        partes = val_str.split(",")
                        parte_inteira = partes[0].replace(".", "")
                        parte_decimal = partes[1] if len(partes) > 1 else "0"
                        val_str = f"{parte_inteira}.{parte_decimal}"

                    # Se tiver só vírgula, converte para ponto decimal
                    elif "," in val_str:
                        val_str = val_str.replace(",", ".")

                    # Converte para número se possível
                    try:
                        novo_valor = float(val_str)
                    except ValueError:
                        novo_valor = val_str
                else:
                    novo_valor = val_str

            # Converte Decimal ou datas para string para comparação segura
            if str(valor_atual) != str(novo_valor):
                alteracoes.append({
                    "campo": field,
                    "valor_antigo": valor_atual,
                    "valor_novo": novo_valor
                })
                setattr(produto, field, novo_valor)
                campos_atualizados.append(field)

        # Se houve alterações, registrar histórico
        if alteracoes:
            for alt in alteracoes:
                hist = ProdutoHistorico(
                    produto_id=produto.id,
                    campo=alt["campo"],
                    valor_antigo=str(alt["valor_antigo"]) if alt["valor_antigo"] is not None else "",
                    valor_novo=str(alt["valor_novo"]) if alt["valor_novo"] is not None else "",
                    usuario_id=current_user.id,
                    usuario_nome=getattr(current_user, "nome", None) or getattr(current_user, "username", None) or str(current_user),
                )
                db.session.add(hist)

        # Atualiza timestamp
        produto.atualizado_em = datetime.utcnow()

        db.session.commit()

        print(f"[M4] Autosave concluído ✅ — campos: {campos_atualizados}")
        return jsonify({
            "success": True,
            "updated": campos_atualizados,
            "atualizado_em": datetime.utcnow().strftime("%d/%m/%Y %H:%M")
        })

    except Exception as e:
        db.session.rollback()
        print("[M4] Erro no autosave:", e)
        return jsonify({"success": False, "error": str(e)}), 500
