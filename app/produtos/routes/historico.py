from flask import jsonify, render_template, current_app
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy.orm import joinedload

from app import db
from .. import produtos_bp
from app.produtos.models import ProdutoHistorico, Produto

# ======================
# REVERTER VALOR DE HISTÓRICO
# ======================
@produtos_bp.route("/historico/<int:hist_id>/reverter", methods=["POST"])
@login_required
def reverter_historico(hist_id):
    """Restaura o valor antigo de um campo no produto, com registro de auditoria."""
    hist = ProdutoHistorico.query.get_or_404(hist_id)
    produto = Produto.query.get(hist.produto_id)

    if not produto:
        return jsonify({"success": False, "error": "Produto não encontrado"}), 404
    if hist.campo == "__acao__":
        return jsonify({"success": False, "error": "Ação de criação não pode ser revertida"}), 400

    try:
        # atualiza o campo no produto
        if hasattr(produto, hist.campo):
            setattr(produto, hist.campo, hist.valor_antigo)
        else:
            return jsonify({"success": False, "error": f"Campo '{hist.campo}' inválido"}), 400

        # registra nova linha de histórico
        reversao = ProdutoHistorico(
            produto_id=produto.id,
            campo=hist.campo,
            valor_antigo=hist.valor_novo,
            valor_novo=hist.valor_antigo,
            usuario_id=getattr(current_user, "id", None),
            usuario_nome=(
                getattr(current_user, "nome", None)
                or getattr(current_user, "username", None)
                or getattr(current_user, "email", None)
            ),
            data_modificacao=datetime.utcnow(),
        )

        db.session.add(reversao)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Campo '{hist.campo}' revertido com sucesso.",
            "campo": hist.campo,
            "valor_novo": hist.valor_antigo,
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao reverter histórico: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ======================
# FRAGMENTO DE HISTÓRICO (AJAX)
# ======================
@produtos_bp.route("/<int:produto_id>/historico/fragment", methods=["GET"])
@login_required
def fragment_historico(produto_id):
    """Retorna o HTML parcial da aba histórico para atualização via AJAX."""
    produto = (
        Produto.query.options(joinedload(Produto.historicos))
        .filter_by(id=produto_id)
        .first()
    )

    if not produto:
        return "<div class='alert alert-danger small'>Produto não encontrado.</div>", 404

    return render_template("produtos/form/abas/_historico.html", produto=produto)


# ======================================================
# HISTÓRICO — CONTADOR RÁPIDO (para atualização dinâmica)
# ======================================================
@produtos_bp.route("/fragment/historico/<int:produto_id>/count")
@login_required
def fragment_historico_count(produto_id):
    """Retorna apenas a contagem de registros do histórico."""
    total = ProdutoHistorico.query.filter_by(produto_id=produto_id).count()
    return jsonify({"count": total})
