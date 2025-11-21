from flask import jsonify
from sqlalchemy import func, extract

from app import db
from app.clientes import clientes_bp
from app.clientes.models import Cliente, Documento, Processo, Comunicacao
from app.vendas.models import Venda
from app.produtos.models import Produto
from app.utils.datetime import now_local


# =================================================
# API — RESUMO (Dashboard)
# =================================================
@clientes_bp.route("/api/resumo")
def api_resumo():
    hoje = now_local()

    clientes_total = db.session.query(func.count(Cliente.id)).scalar()

    documentos_validos = (
        db.session.query(func.count(Documento.id))
        .filter(Documento.data_validade >= hoje)
        .scalar()
    )

    documentos_vencidos = (
        db.session.query(func.count(Documento.id))
        .filter(Documento.data_validade < hoje)
        .scalar()
    )

    produtos_total = db.session.query(func.count(Produto.id)).scalar()

    processos_ativos = (
        db.session.query(func.count(Processo.id))
        .filter(func.lower(Processo.status).notin_(["concluído", "finalizado"]))
        .scalar()
    )

    vendas_mes = (
        db.session.query(func.sum(Venda.valor_total))
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .scalar()
        or 0
    )

    return jsonify({
        "clientes_total": clientes_total or 0,
        "documentos_validos": documentos_validos or 0,
        "documentos_vencidos": documentos_vencidos or 0,
        "produtos_total": produtos_total or 0,
        "processos_ativos": processos_ativos or 0,
        "vendas_mes": float(vendas_mes),
    })


# =================================================
# API — ALERTAS DO SISTEMA
# =================================================
@clientes_bp.route("/api/alertas")
def api_alertas():
    from app.utils.alertas import gerar_alertas_gerais
    alertas = gerar_alertas_gerais()
    return jsonify({"alertas": alertas})


# =================================================
# API — TIMELINE GLOBAL
# =================================================
@clientes_bp.route("/api/timeline")
def api_timeline():
    eventos = []

    # 1. Documentos recentes
    docs = Documento.query.filter(Documento.data_upload != None).limit(5).all()
    for d in docs:
        eventos.append({
            "data": d.data_upload.isoformat(),
            "tipo": "documento",
            "descricao": f"Upload de {d.tipo or d.categoria} - {d.cliente.nome}"
        })

    # 2. Processos recentes
    procs = Processo.query.limit(5).all()
    for p in procs:
        eventos.append({
            "data": p.data.isoformat() if p.data else None,
            "tipo": "processo",
            "descricao": f"{p.tipo} ({p.status}) - {p.cliente.nome}"
        })

    # 3. Vendas recentes
    vendas = Venda.query.limit(5).all()
    for v in vendas:
        eventos.append({
            "data": v.data_abertura.isoformat() if v.data_abertura else None,
            "tipo": "venda",
            "descricao": f"Venda #{v.id} - {v.cliente.nome if v.cliente else 'Cliente não identificado'}"
        })

    # 4. Comunicações recentes
    comunicacoes = Comunicacao.query.limit(5).all()
    for c in comunicacoes:
        eventos.append({
            "data": c.data.isoformat() if c.data else None,
            "tipo": "comunicacao",
            "descricao": f"{c.assunto or 'Comunicação'} - {c.cliente.nome}"
        })

    # Ordena por data (desc) e limita globalmente
    eventos = sorted(
        [e for e in eventos if e.get("data")],
        key=lambda x: x["data"],
        reverse=True
    )[:10]

    return jsonify({"eventos": eventos})
