# ============================================================
# app/importacoes/routes.py
# ============================================================

from flask import render_template, request, send_file, jsonify, current_app
from flask_login import login_required
from io import StringIO
import csv
from app import db
from app.importacoes import importacoes_bp
from app.importacoes.models import ImportacaoLog


# ============================================================
# ROTA: Lista de importações (completa)
# ============================================================
@importacoes_bp.route("/", methods=["GET"], endpoint="listar")
@login_required
def listar_importacoes():
    """Lista completa de importações, filtrável por tipo."""
    tipo = request.args.get("tipo", None)
    query = ImportacaoLog.query.order_by(ImportacaoLog.data_hora.desc())
    if tipo:
        query = query.filter_by(tipo=tipo)

    logs = query.limit(200).all()
    return render_template("importacoes/listar.html", logs=logs, tipo=tipo)


# ============================================================
# ROTA: API — Últimas Importações (para Dashboard)
# ============================================================
@importacoes_bp.route("/api/ultimas", methods=["GET"], endpoint="api_ultimas")
@login_required
def api_ultimas():
    """Retorna as últimas importações (JSON) para o dashboard."""
    ultimas = (
        ImportacaoLog.query.order_by(ImportacaoLog.data_hora.desc()).limit(5).all()
    )
    return jsonify([i.to_dict() for i in ultimas])


# ============================================================
# ROTA: Exportar CSV
# ============================================================
@importacoes_bp.route("/exportar_csv", methods=["GET"], endpoint="exportar_csv")
@login_required
def exportar_csv():
    """Exporta todos os registros de importações em CSV."""
    registros = ImportacaoLog.query.order_by(ImportacaoLog.data_hora.desc()).all()

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer, delimiter=";")
    writer.writerow(["ID", "Tipo", "Usuário", "Data/Hora", "Novos", "Atualizados", "Total"])

    for r in registros:
        writer.writerow([
            r.id,
            r.tipo,
            r.usuario or "-",
            r.data_hora.strftime("%d/%m/%Y %H:%M") if r.data_hora else "",
            r.novos,
            r.atualizados,
            r.total,
        ])

    csv_buffer.seek(0)
    return send_file(
        StringIO(csv_buffer.getvalue()),
        as_attachment=True,
        download_name="importacoes_log.csv",
        mimetype="text/csv",
    )
