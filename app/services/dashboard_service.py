# app/services/dashboard_service.py

from datetime import datetime, timedelta

from sqlalchemy import func, extract

from app.extensions import db
from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.vendas.models import Venda, ItemVenda
from app.clientes.models import Cliente
from app.models import Notificacao


# ============================
# Helpers internos
# ============================

_MAPA_MESES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez"
]


def _mes_numero_para_nome(mes_num: int) -> str:
    """Converte número do mês (1-12) para nome abreviado em PT-BR."""
    if not mes_num or mes_num < 1 or mes_num > 12:
        return str(mes_num)
    return _MAPA_MESES[mes_num - 1]


# ============================
# Dashboard HTML principal
# ============================

def get_dashboard_context():
    """
    Calcula todos os dados necessários para renderizar o dashboard.html.

    Retorna um dict com todas as chaves esperadas pelo template:
      - produtos
      - total_vendas_mes
      - top_clientes
      - produto_mais_vendido
      - ticket_medio
      - meses
      - totais
      - notificacoes_pendentes
    """
    hoje = datetime.today()

    # Lista de produtos
    produtos = Produto.query.all()

    # Total de vendas no mês atual
    total_vendas_mes = (
        db.session.query(func.sum(Venda.valor_total))
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .scalar()
        or 0
    )

    # Ticket médio geral
    ticket_medio = (
        db.session.query(func.sum(Venda.valor_total) / func.count(Venda.id))
        .scalar()
        or 0
    )

    # Top 5 clientes por valor de venda
    top_clientes = (
        db.session.query(Cliente.nome, func.sum(Venda.valor_total).label("total"))
        .join(Venda, Cliente.id == Venda.cliente_id)
        .group_by(Cliente.id)
        .order_by(func.sum(Venda.valor_total).desc())
        .limit(5)
        .all()
    )

    # Produto mais vendido (por quantidade)
    produto_mais_vendido = (
        db.session.query(
            ItemVenda.produto_nome,
            func.sum(ItemVenda.quantidade).label("qtd")
        )
        .group_by(ItemVenda.produto_nome)
        .order_by(func.sum(ItemVenda.quantidade).desc())
        .first()
    )

    # Vendas por mês (últimos 180 dias)
    vendas_por_mes = (
        db.session.query(
            extract("month", Venda.data_abertura).label("mes"),
            func.sum(Venda.valor_total).label("total"),
        )
        .filter(Venda.data_abertura >= hoje - timedelta(days=180))
        .group_by(extract("month", Venda.data_abertura))
        .order_by(extract("month", Venda.data_abertura))
        .all()
    )

    meses_nomes = []
    totais = []

    for mes_num, total in vendas_por_mes:
        # mes_num vem como algo tipo Decimal ou float; convertemos para int
        try:
            mes_int = int(mes_num)
        except (TypeError, ValueError):
            mes_int = None

        meses_nomes.append(_mes_numero_para_nome(mes_int))
        totais.append(float(total or 0))

    # Notificações pendentes
    notificacoes_pendentes = Notificacao.query.filter_by(status="enviado").count()

    return {
        "produtos": produtos,
        "total_vendas_mes": total_vendas_mes,
        "top_clientes": top_clientes,
        "produto_mais_vendido": produto_mais_vendido,
        "ticket_medio": ticket_medio,
        "meses": meses_nomes,
        "totais": totais,
        "notificacoes_pendentes": notificacoes_pendentes,
    }


# ============================
# API: Resumo (KPIs)
# ============================

def get_dashboard_resumo():
    """
    Calcula os agregados usados na API /dashboard/api/resumo.

    Retorna um dict serializável em JSON com:
      - produtos_total
      - clientes_total
      - documentos_validos
      - documentos_vencidos
      - vendas_mes
      - ticket_medio
      - categorias: lista de {nome, total}
    """
    hoje = datetime.today()

    # Totais básicos
    total_produtos = db.session.query(func.count(Produto.id)).scalar() or 0
    total_clientes = db.session.query(func.count(Cliente.id)).scalar() or 0

    # Documentos (simplificação atual baseada em Venda)
    um_ano_atras = hoje - timedelta(days=365)

    documentos_validos = (
        db.session.query(func.count(Venda.id))
        .filter(Venda.data_fechamento >= um_ano_atras)
        .scalar()
        or 0
    )

    documentos_vencidos = (
        db.session.query(func.count(Venda.id))
        .filter(Venda.data_fechamento < um_ano_atras)
        .scalar()
        or 0
    )

    # Vendas e ticket médio do mês atual
    vendas_mes = (
        db.session.query(func.sum(Venda.valor_total))
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .scalar()
        or 0
    )

    ticket_medio = (
        db.session.query(func.sum(Venda.valor_total) / func.count(Venda.id))
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .scalar()
        or 0
    )

    # Produtos por categoria
    try:
        categorias_data = (
            db.session.query(
                func.coalesce(CategoriaProduto.nome, "Sem categoria").label("nome"),
                func.count(Produto.id).label("total"),
            )
            .outerjoin(CategoriaProduto, CategoriaProduto.id == Produto.categoria_id)
            .group_by(CategoriaProduto.nome)
            .order_by(func.count(Produto.id).desc())
            .all()
        )
    except Exception:
        categorias_data = []

    categorias = [
        {"nome": nome or "Sem categoria", "total": int(total or 0)}
        for nome, total in categorias_data
    ]

    return {
        "produtos_total": int(total_produtos),
        "clientes_total": int(total_clientes),
        "documentos_validos": int(documentos_validos),
        "documentos_vencidos": int(documentos_vencidos),
        "vendas_mes": float(vendas_mes or 0),
        "ticket_medio": float(ticket_medio or 0),
        "categorias": categorias,
    }


# ============================
# API: Timeline
# ============================

def get_dashboard_timeline():
    """
    Monta a lista de eventos recentes para a timeline.

    Retorna um dict:
      - eventos: lista de dicts {tipo, descricao, data}
    """
    eventos = []

    # Últimas vendas
    ultimas_vendas = (
        db.session.query(Venda)
        .order_by(Venda.data_abertura.desc())
        .limit(5)
        .all()
    )
    for v in ultimas_vendas:
        if not v.data_abertura:
            continue
        eventos.append({
            "tipo": "venda",
            "descricao": f"Venda #{v.id} registrada no valor de R$ {float(v.valor_total or 0):.2f}",
            "data": v.data_abertura.isoformat(),
        })

    # Últimos produtos cadastrados
    ultimos_produtos = (
        db.session.query(Produto)
        .order_by(Produto.criado_em.desc())
        .limit(5)
        .all()
    )
    for p in ultimos_produtos:
        if not p.criado_em:
            continue
        eventos.append({
            "tipo": "produto",
            "descricao": f"Produto '{p.nome}' cadastrado.",
            "data": p.criado_em.isoformat(),
        })

    # Últimos clientes (sem campo explícito de criação, usa data atual)
    ultimos_clientes = (
        db.session.query(Cliente)
        .order_by(Cliente.id.desc())
        .limit(5)
        .all()
    )
    agora = datetime.today()
    for c in ultimos_clientes:
        eventos.append({
            "tipo": "cliente",
            "descricao": f"Novo cliente cadastrado: {c.nome}",
            "data": agora.isoformat(),
        })

    # Ordena por data decrescente e limita a 10 eventos
    eventos.sort(key=lambda x: x["data"], reverse=True)
    return {
        "eventos": eventos[:10],
    }
