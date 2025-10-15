# ======================
# NOTIFICAÇÕES - ROTAS
# ======================

from flask import render_template, jsonify, request
from app.notificacoes import notificacoes_bp
from app.alertas.notificacoes import listar_notificacoes
from flask_login import login_required


# -------------------------
# 🔹 Rota: Página principal
# -------------------------
@notificacoes_bp.route("/")
@login_required
def index():
    """
    Exibe o painel principal de notificações.
    (Fase inicial: apenas estrutura HTML simples)
    """
    return render_template("notificacoes.html", titulo="Painel de Notificações")


# -------------------------
# 🔹 API: Listar notificações
# -------------------------
@notificacoes_bp.route("/api")
@login_required
def api_listar_notificacoes():
    """
    Retorna notificações em formato JSON, com suporte a filtros e paginação.
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    filtros = {
        "tipo": request.args.get("tipo", "").strip() or None,
        "nivel": request.args.get("nivel", "").strip() or None,
        "meio": request.args.get("meio", "").strip() or None,
        "status": request.args.get("status", "").strip() or None,
        "q": request.args.get("q", "").strip() or None,
    }

    data = listar_notificacoes(filtros=filtros, page=page, per_page=per_page)
    return jsonify(data)

# -------------------------
# 🔹 API: Marcar notificação como lida
# -------------------------
@notificacoes_bp.route("/api/<int:notificacao_id>/lida", methods=["PATCH"])
@login_required
def marcar_notificacao_lida(notificacao_id):
    """
    Atualiza o status da notificação para 'lido'.
    Retorna JSON com resultado da operação.
    """
    from app.models import Notificacao  # import local para evitar circular
    from app.extensions import db

    notif = Notificacao.query.get(notificacao_id)
    if not notif:
        return jsonify({"error": "Notificação não encontrada"}), 404

    notif.status = "lido"
    db.session.commit()

    return jsonify({
        "success": True,
        "id": notif.id,
        "status": notif.status,
        "data_envio": notif.data_envio.isoformat()
    })
# ======================
# Marcar notificação como lida (AJAX)
# ======================
from datetime import datetime
from flask import jsonify
from flask_login import login_required
from app.models import Notificacao
from app.extensions import db

@notificacoes_bp.route("/api/<int:notificacao_id>/lida", methods=["POST"])
@login_required
def marcar_como_lida(notificacao_id):
    """Marca uma notificação como lida e retorna JSON atualizado."""
    notif = Notificacao.query.get_or_404(notificacao_id)

    if notif.status != "lido":
        notif.status = "lido"
        notif.data_envio = notif.data_envio or datetime.utcnow()
        db.session.commit()

    return jsonify({
        "success": True,
        "id": notif.id,
        "status": notif.status,
        "mensagem": notif.mensagem,
    })

