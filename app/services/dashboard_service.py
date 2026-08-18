# app/services/dashboard_service.py

from datetime import datetime, timedelta

from sqlalchemy import func, extract, or_

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
    Otimizado para performance: evita Produto.query.all() e usa agregados.
    """
    hoje = datetime.today()

    # KPIs rápidos (Contagens)
    total_produtos = db.session.query(func.count(Produto.id)).scalar() or 0
    total_clientes = db.session.query(func.count(Cliente.id)).scalar() or 0
    notificacoes_pendentes = Notificacao.query.filter_by(status="enviado").count()

    # Total de vendas no mês atual
    total_vendas_mes = (
        db.session.query(func.sum(Venda.valor_total))
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .scalar()
        or 0
    )

    # Ticket médio do mês
    ticket_medio = (
        db.session.query(func.sum(Venda.valor_total) / func.count(Venda.id))
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .scalar()
        or 0
    )

    # Top 5 clientes (Valor total em vendas)
    top_clientes = (
        db.session.query(Cliente.nome, func.sum(Venda.valor_total).label("total"))
        .join(Venda, Cliente.id == Venda.cliente_id)
        .group_by(Cliente.id)
        .order_by(func.sum(Venda.valor_total).desc())
        .limit(5)
        .all()
    )

    # Vendas por mês (últimos 6 meses)
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
        try:
            mes_int = int(mes_num)
        except (TypeError, ValueError):
            mes_int = None
        meses_nomes.append(_mes_numero_para_nome(mes_int))
        totais.append(float(total or 0))

    # Documentos a vencer (próximos 30 dias)
    from app.clientes.models import Documento
    trinta_dias = hoje.date() + timedelta(days=30)
    docs_a_vencer = Documento.query.filter(
        Documento.data_validade >= hoje.date(),
        Documento.data_validade <= trinta_dias,
        Documento.validade_indeterminada == False
    ).order_by(Documento.data_validade.asc()).limit(5).all()

    return {
        "total_produtos": total_produtos,
        "total_clientes": total_clientes,
        "total_vendas_mes": total_vendas_mes,
        "top_clientes": top_clientes,
        "ticket_medio": ticket_medio,
        "meses": meses_nomes,
        "totais": totais,
        "notificacoes_pendentes": notificacoes_pendentes,
        "docs_a_vencer": docs_a_vencer
    }


# ============================
# API: Resumo (KPIs)
# ============================

def get_dashboard_resumo():
    """
    Calcula os agregados usados na API /dashboard/api/resumo.
    Otimizado para usar a tabela de Documentos e Armas real.
    """
    hoje = datetime.today().date()

    # Totais básicos
    total_produtos = db.session.query(func.count(Produto.id)).scalar() or 0
    total_clientes = db.session.query(func.count(Cliente.id)).scalar() or 0

    # Documentos reais (tabela documentos)
    from app.clientes.models import Documento, Arma
    
    docs_vencidos = db.session.query(func.count(Documento.id)).filter(
        Documento.data_validade < hoje,
        Documento.validade_indeterminada == False
    ).scalar() or 0
    
    docs_validos = db.session.query(func.count(Documento.id)).filter(
        or_(Documento.data_validade >= hoje, Documento.validade_indeterminada == True)
    ).scalar() or 0

    # Armas cadastradas
    total_armas = db.session.query(func.count(Arma.id)).scalar() or 0

    # Vendas do mês
    vendas_mes = (
        db.session.query(func.sum(Venda.valor_total))
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .scalar()
        or 0
    )

    # Ticket médio do mês
    ticket_medio = (
        db.session.query(func.sum(Venda.valor_total) / func.count(Venda.id))
        .filter(extract("month", Venda.data_abertura) == hoje.month)
        .filter(extract("year", Venda.data_abertura) == hoje.year)
        .scalar()
        or 0
    )

    return {
        "produtos_total": int(total_produtos),
        "clientes_total": int(total_clientes),
        "documentos_validos": int(docs_validos),
        "documentos_vencidos": int(docs_vencidos),
        "total_armas": int(total_armas),
        "vendas_mes": float(vendas_mes or 0),
        "ticket_medio": float(ticket_medio or 0),
        "categorias": get_produtos_por_categoria()
    }

def get_produtos_por_categoria():
    try:
        data = (
            db.session.query(
                func.coalesce(CategoriaProduto.nome, "Sem categoria").label("nome"),
                func.count(Produto.id).label("total"),
            )
            .outerjoin(CategoriaProduto, CategoriaProduto.id == Produto.categoria_id)
            .group_by(CategoriaProduto.nome)
            .order_by(func.count(Produto.id).desc())
            .limit(10)
            .all()
        )
        return [{"nome": n, "total": t} for n, t in data]
    except:
        return []

def global_search(termo):
    """
    Motor de busca global unificado para o dashboard.
    Busca em Clientes, Documentos, Armas, Munições e Produtos.
    """
    if not termo or len(termo) < 2:
        return []

    from app.clientes.models import Documento, Arma
    from app.estoque.models import ItemEstoque
    from app.produtos.configs.models import MarcaProduto, CalibreProduto
    busca_like = f"%{termo}%"
    
    resultados = []

    # 1. Clientes (Nome, CPF, Apelido)
    clientes = Cliente.query.filter(
        or_(
            Cliente.nome.ilike(busca_like),
            Cliente.documento.ilike(busca_like),
            Cliente.apelido.ilike(busca_like)
        )
    ).limit(5).all()
    for c in clientes:
        resultados.append({
            "tipo": "cliente",
            "titulo": c.nome,
            "subtitulo": f"CPF: {c.documento}",
            "link": f"/clientes/{c.id}"
        })

    # 2. Armas (Série, Modelo)
    armas = Arma.query.filter(
        or_(
            Arma.numero_serie.ilike(busca_like),
            Arma.modelo.ilike(busca_like)
        )
    ).limit(5).all()
    for a in armas:
        resultados.append({
            "tipo": "arma",
            "titulo": f"{a.marca} {a.modelo}",
            "subtitulo": f"Série: {a.numero_serie} | Cliente: {a.cliente.nome}",
            "link": f"/clientes/{a.cliente_id}"
        })

    # 3. Munições e Lotes (ItemEstoque)
    itens = ItemEstoque.query.filter(
        or_(
            ItemEstoque.lote.ilike(busca_like),
            ItemEstoque.numero_serie.ilike(busca_like),
            ItemEstoque.numero_selo.ilike(busca_like)
        )
    ).limit(5).all()
    for i in itens:
        resultados.append({
            "tipo": "municao",
            "titulo": f"{i.produto.nome}",
            "subtitulo": f"Lote: {i.lote} | Selo: {i.numero_selo}",
            "link": f"/produtos/{i.produto_id}/editar"
        })

    # 4. Documentos (Número)
    docs = Documento.query.filter(Documento.numero_documento.ilike(busca_like)).limit(5).all()
    for d in docs:
        resultados.append({
            "tipo": "documento",
            "titulo": f"{d.tipo}: {d.numero_documento}",
            "subtitulo": f"Cliente: {d.cliente.nome}",
            "link": f"/clientes/{d.cliente_id}"
        })

    # 5. Produtos (Catálogo Geral) - PRIORIDADE MÁXIMA
    # Buscamos em Nome, Código, Marca, Calibre e Palavras-chave
    produtos = Produto.query.join(Produto.marca_rel, isouter=True)\
                            .join(Produto.calibre_rel, isouter=True).filter(
        or_(
            Produto.nome.ilike(busca_like),
            Produto.codigo.ilike(busca_like),
            Produto.nome_comercial.ilike(busca_like),
            Produto.tags_palavras_chave.ilike(busca_like),
            MarcaProduto.nome.ilike(busca_like),
            CalibreProduto.nome.ilike(busca_like)
        )
    ).limit(20).all()
    
    for p in produtos:
        resultados.insert(0, {
            "tipo": "produto",
            "titulo": p.nome_comercial or p.nome,
            "subtitulo": f"REF: {p.codigo} | R$ {p.preco_a_vista:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "link": f"/produtos/{p.id}/editar"
        })

    return resultados


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
