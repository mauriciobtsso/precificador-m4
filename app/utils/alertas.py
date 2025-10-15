# ===========================
# UTILS: ALERTAS DO SISTEMA (v3 Integrado e Otimizado)
# ===========================

from datetime import datetime, timedelta
from app.clientes.models import Cliente, Documento, Arma, Processo
from app.models import Venda
from app.extensions import db


# ==========================================================
# FUNÇÃO PRINCIPAL - GERA ALERTAS INTELIGENTES (v4 Otimizada)
# ==========================================================
from datetime import datetime, timedelta
from app.clientes.models import Cliente, Documento, Arma, Processo
from app.extensions import db


def gerar_alertas_gerais(filtros=None, page=1, per_page=20):
    """
    Gera lista consolidada e paginada de alertas RELEVANTES:
      ✅ Clientes com documentos válidos, vencidos ou próximos do vencimento
      ✅ Armas com CRAF vencido / a vencer
      ✅ Processos em andamento
    Ignora clientes sem documento, ou com documentos longe do vencimento.

    Filtros: tipo, nivel, q, inicio, fim (dinâmicos)
    """

    hoje = datetime.now().date()
    alertas = []

    # ==========================================================
    # 1️⃣ DOCUMENTOS RELEVANTES (núcleo da filtragem)
    # ==========================================================
    documentos_relevantes = (
        Documento.query
        .join(Cliente)
        .filter(Documento.data_validade.isnot(None))
        .filter(Documento.data_validade >= hoje - timedelta(days=90))  # ignora antigos
        .filter(Documento.data_validade <= hoje + timedelta(days=60))  # só próximos
        .all()
    )

    for d in documentos_relevantes:
        dias_restantes = (d.data_validade - hoje).days
        cliente_nome = d.cliente.nome if d.cliente else "—"

        if d.data_validade < hoje:
            nivel = "alto"
            mensagem = f"Documento '{d.tipo or d.categoria}' de {cliente_nome} vencido em {d.data_validade.strftime('%d/%m/%Y')}"
        elif dias_restantes <= 15:
            nivel = "médio"
            mensagem = f"Documento '{d.tipo or d.categoria}' de {cliente_nome} vence em {d.data_validade.strftime('%d/%m/%Y')}"
        else:
            nivel = "baixo"
            mensagem = f"Documento '{d.tipo or d.categoria}' de {cliente_nome} vence em {d.data_validade.strftime('%d/%m/%Y')}"

        alertas.append({
            "tipo": "documento",
            "subtipo": d.tipo or d.categoria,
            "nivel": nivel,
            "mensagem": mensagem,
            "cliente": cliente_nome,
            "cliente_id": d.cliente_id,
            "data": d.data_validade.strftime("%Y-%m-%d"),
            "dias_restantes": dias_restantes,
        })

    # ==========================================================
    # 2️⃣ ARMAS COM CRAF VENCIDO / PRÓXIMO
    # ==========================================================
    armas_relevantes = (
        Arma.query
        .join(Cliente)
        .filter(Arma.data_validade_craf.isnot(None))
        .filter(Arma.data_validade_craf >= hoje - timedelta(days=90))
        .filter(Arma.data_validade_craf <= hoje + timedelta(days=60))
        .all()
    )

    for a in armas_relevantes:
        dias_restantes = (a.data_validade_craf - hoje).days
        cliente_nome = a.cliente.nome if a.cliente else "—"

        if a.data_validade_craf < hoje:
            nivel = "alto"
            mensagem = f"CRAF de {cliente_nome} vencido em {a.data_validade_craf.strftime('%d/%m/%Y')}"
        elif dias_restantes <= 15:
            nivel = "médio"
            mensagem = f"CRAF de {cliente_nome} vence em {a.data_validade_craf.strftime('%d/%m/%Y')}"
        else:
            nivel = "baixo"
            mensagem = f"CRAF de {cliente_nome} vence em {a.data_validade_craf.strftime('%d/%m/%Y')}"

        alertas.append({
            "tipo": "arma",
            "subtipo": "craf",
            "nivel": nivel,
            "mensagem": mensagem,
            "cliente": cliente_nome,
            "cliente_id": a.cliente_id,
            "data": a.data_validade_craf.strftime("%Y-%m-%d"),
            "dias_restantes": dias_restantes,
        })

    # ==========================================================
    # 3️⃣ PROCESSOS EM ANDAMENTO (apenas clientes já relevantes)
    # ==========================================================
    clientes_relevantes_ids = {a["cliente_id"] for a in alertas}

    processos = (
        Processo.query
        .join(Cliente)
        .filter(db.func.lower(Processo.status).notin_(["concluído", "finalizado"]))
        .filter(Processo.cliente_id.in_(clientes_relevantes_ids))
        .all()
    )

    for p in processos:
        alertas.append({
            "tipo": "processo",
            "subtipo": p.tipo,
            "nivel": "baixo",
            "mensagem": f"Processo '{p.tipo}' em andamento ({p.status}) — {p.cliente.nome}",
            "cliente": p.cliente.nome,
            "cliente_id": p.cliente_id,
            "data": hoje.strftime("%Y-%m-%d"),
            "dias_restantes": None,
        })

    # ==========================================================
    # 🔍 FILTROS DINÂMICOS (tipo, nivel, q, inicio, fim)
    # ==========================================================
    if filtros:
        tipo = filtros.get("tipo")
        nivel = filtros.get("nivel")
        q = filtros.get("q", "").lower() if filtros.get("q") else None
        inicio = filtros.get("inicio")
        fim = filtros.get("fim")

        if tipo:
            alertas = [a for a in alertas if a["tipo"] == tipo]
        if nivel:
            alertas = [a for a in alertas if a["nivel"] == nivel]
        if q:
            alertas = [a for a in alertas if q in a["cliente"].lower() or q in a["mensagem"].lower()]
        if inicio:
            alertas = [a for a in alertas if a["data"] >= inicio]
        if fim:
            alertas = [a for a in alertas if a["data"] <= fim]

    # ==========================================================
    # 🔢 ORDENAÇÃO E PAGINAÇÃO
    # ==========================================================
    nivel_ordem = {"alto": 1, "médio": 2, "medio": 2, "baixo": 3}
    alertas = sorted(
        alertas,
        key=lambda x: (nivel_ordem.get(x["nivel"], 4), x["dias_restantes"] or 9999)
    )

    total = len(alertas)
    inicio_idx = (page - 1) * per_page
    fim_idx = inicio_idx + per_page
    paginados = alertas[inicio_idx:fim_idx]

    # ==========================================================
    # 🔁 RETORNO PADRONIZADO
    # ==========================================================
    return {
        "page": page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "total": total,
        "data": paginados,
    }
