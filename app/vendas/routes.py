from flask import render_template, request
from flask_login import login_required
from app.extensions import db
from app.vendas.models import Venda, ItemVenda
from app.clientes.models import Cliente
from . import vendas_bp
from datetime import datetime, timedelta
from sqlalchemy import extract


# =========================
# LISTAGEM DE VENDAS + RESUMO
# =========================
@vendas_bp.route("/", methods=["GET", "POST"])
@login_required
def vendas():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    query = Venda.query.join(Cliente, isouter=True)

    # --- Filtros ---
    cliente_nome = request.args.get("cliente", "").strip()
    status = request.args.get("status", "").strip()
    periodo = request.args.get("periodo", "").strip()
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    if cliente_nome:
        query = query.filter(Cliente.nome.ilike(f"%{cliente_nome}%"))
    if status:
        query = query.filter(Venda.status.ilike(f"%{status}%"))

    hoje = datetime.today()
    if periodo == "7d":
        query = query.filter(Venda.data_abertura >= hoje - timedelta(days=7))
    elif periodo == "mes":
        query = query.filter(
            extract("year", Venda.data_abertura) == hoje.year,
            extract("month", Venda.data_abertura) == hoje.month
        )
    elif periodo == "personalizado" and data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Venda.data_abertura >= inicio, Venda.data_abertura < fim)
        except Exception:
            pass

    # --- Paginação ---
    vendas_paginadas = query.order_by(Venda.data_abertura.desc()).paginate(page=page, per_page=per_page)

    # --- Resumo agregado ---
    vendas_filtradas = query.all()
    total_vendas = len(vendas_filtradas)
    soma_total = sum(v.valor_total or 0 for v in vendas_filtradas)
    soma_descontos = sum(v.desconto_valor or 0 for v in vendas_filtradas)
    soma_recebido = sum(v.valor_recebido or 0 for v in vendas_filtradas)
    media_venda = soma_total / total_vendas if total_vendas > 0 else 0

    resumo = {
        "total_vendas": total_vendas,
        "soma_total": soma_total,
        "soma_descontos": soma_descontos,
        "soma_recebido": soma_recebido,
        "media_venda": media_venda,
    }

    return render_template(
        "vendas/index.html",
        vendas=vendas_paginadas,
        resumo=resumo,
        cliente_nome=cliente_nome,
        status=status,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


# =========================
# DETALHE DE VENDA
# =========================
@vendas_bp.route("/<int:venda_id>")
@login_required
def venda_detalhe(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    cliente = Cliente.query.get(venda.cliente_id) if venda.cliente_id else None
    itens = ItemVenda.query.filter_by(venda_id=venda.id).all()

    return render_template(
        "vendas/detalhe.html",
        venda=venda,
        cliente=cliente,
        itens=itens
    )
