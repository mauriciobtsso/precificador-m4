# ============================================================
# app/importacoes/routes.py
# ============================================================

from flask import render_template, request, send_file, jsonify
from flask_login import login_required
from datetime import datetime, timedelta
from io import StringIO
import csv
from app import db
from app.importacoes import importacoes_bp
from app.importacoes.models import ImportacaoLog


# ============================================================
# ROTA: Lista de importações (com filtros e paginação)
# ============================================================
@importacoes_bp.route("/", methods=["GET"], endpoint="listar")
@login_required
def listar_importacoes():
    """Lista completa de importações com filtros de tipo, data e paginação."""
    tipo = request.args.get("tipo") or None
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")
    page = request.args.get("page", 1, type=int)
    per_page = 25

    # Base query ordenada por data mais recente
    query = ImportacaoLog.query.order_by(ImportacaoLog.data_hora.desc())

    # Filtro por tipo
    if tipo:
        query = query.filter(ImportacaoLog.tipo == tipo)

    # Filtro por data inicial
    if data_ini:
        try:
            data_ini_dt = datetime.strptime(data_ini, "%Y-%m-%d")
            query = query.filter(ImportacaoLog.data_hora >= data_ini_dt)
        except ValueError:
            pass

    # Filtro por data final (inclusivo)
    if data_fim:
        try:
            data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(ImportacaoLog.data_hora < data_fim_dt)
        except ValueError:
            pass

    # Paginação
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items

    return render_template(
        "importacoes/listar.html",
        logs=logs,
        tipo=tipo,
        data_ini=data_ini,
        data_fim=data_fim,
        pagination=pagination,
    )


# ============================================================
# ROTA: API — Últimas Importações (para Dashboard)
# ============================================================
@importacoes_bp.route("/api/ultimas", methods=["GET"], endpoint="api_ultimas")
@login_required
def api_ultimas():
    """Retorna as últimas importações em JSON para o dashboard."""
    ultimas = (
        ImportacaoLog.query.order_by(ImportacaoLog.data_hora.desc()).limit(5).all()
    )
    return jsonify([i.to_dict() for i in ultimas])


# ============================================================
# ROTA: Exportar CSV (revisado - usa BytesIO)
# ============================================================
@importacoes_bp.route("/exportar_csv", methods=["GET"], endpoint="exportar_csv")
@login_required
def exportar_csv():
    """Exporta registros de importações em CSV, respeitando filtros."""
    tipo = request.args.get("tipo")
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    query = ImportacaoLog.query.order_by(ImportacaoLog.data_hora.desc())

    # Filtros aplicados também na exportação
    if tipo:
        query = query.filter(ImportacaoLog.tipo == tipo)

    if data_ini:
        try:
            data_ini_dt = datetime.strptime(data_ini, "%Y-%m-%d")
            query = query.filter(ImportacaoLog.data_hora >= data_ini_dt)
        except ValueError:
            pass

    if data_fim:
        try:
            data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(ImportacaoLog.data_hora < data_fim_dt)
        except ValueError:
            pass

    registros = query.all()

    # Gera CSV em memória (texto)
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

    # Converte para bytes antes de enviar
    from io import BytesIO
    binary_buffer = BytesIO()
    binary_buffer.write(csv_buffer.getvalue().encode("utf-8"))
    binary_buffer.seek(0)

    return send_file(
        binary_buffer,
        as_attachment=True,
        download_name="importacoes_log.csv",
        mimetype="text/csv"
    )
