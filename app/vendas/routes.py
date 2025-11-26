from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.vendas.models import Venda, ItemVenda
from app.clientes.models import Cliente, Arma
from app.produtos.models import Produto
from app.estoque.models import ItemEstoque
from app.services.venda_service import VendaService
from . import vendas_bp
import re
from datetime import datetime, timedelta
from sqlalchemy import extract, func


# ===============================================================
#  TELAS (HTML)
# ===============================================================

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

    # --- Resumo agregado OTIMIZADO (SQL) ---
    resumo_dados = query.with_entities(
        func.count(Venda.id).label('total'),
        func.sum(Venda.valor_total).label('soma_total'),
        func.sum(Venda.desconto_valor).label('soma_descontos'),
        func.sum(Venda.valor_recebido).label('soma_recebido')
    ).first()

    total_vendas = resumo_dados.total or 0
    soma_total = resumo_dados.soma_total or 0
    soma_descontos = resumo_dados.soma_descontos or 0
    soma_recebido = resumo_dados.soma_recebido or 0
    
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


@vendas_bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova_venda():
    if request.method == "POST":
        dados = request.get_json()
        try:
            venda = VendaService.criar_venda(dados, current_user)
            return jsonify({"success": True, "venda_id": venda.id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
            
    return render_template("vendas/form.html")

@vendas_bp.route("/<int:venda_id>/editar", methods=["GET", "POST"])
@login_required
def editar_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    
    # Nota: Se o formulário de venda usa muito JavaScript (venda_form.js) para montar o carrinho,
    # editar uma venda existente requer que passamos os dados pré-populados para o JS.
    # Por enquanto, estamos redirecionando para o formulário. 
    # (Desenvolvimento futuro: garantir que 'form.html' saiba ler 'venda.itens' e popular o carrinho)
    
    if request.method == "POST":
        # Lógica de salvar edição viria aqui
        pass

    return render_template("vendas/form.html", venda=venda, edicao=True)

@vendas_bp.route("/<int:venda_id>/excluir", methods=["POST"])
@login_required
def excluir_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    
    try:
        # Opcional: Adicionar lógica para estornar o estoque aqui se a venda não foi cancelada antes
        # if venda.status != 'cancelada':
        #     for item in venda.itens:
        #         devolver_estoque(item)

        db.session.delete(venda)
        db.session.commit()
        flash(f"Venda #{venda_id} excluída com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir venda: {str(e)}", "danger")
        
    return redirect(url_for("vendas.vendas"))


# ===============================================================
#  APIs INTERNAS (JSON) - Usadas pelo JavaScript do Formulário
# ===============================================================

@vendas_bp.route("/api/clientes")
@login_required
def api_buscar_clientes():
    termo = request.args.get("q", "")
    clientes = Cliente.query.filter(
        (Cliente.nome.ilike(f"%{termo}%")) | 
        (Cliente.documento.ilike(f"%{termo}%"))
    ).limit(10).all()
    
    return jsonify([{
        "id": c.id, 
        "nome": c.nome, 
        "documento": c.documento,
        "cr": c.cr
    } for c in clientes])


# --- Lógica de Calibre ---
def normalizar_calibre(texto):
    if not texto:
        return ""
    limpo = texto.lower().replace(".", "").replace("-", "").replace(" ", "")
    termos_para_remover = [
        "acp", "auto", "spl", "special", "win", "rem", "magnum", 
        "parabellum", "luger", "mm", "ga", "gauge", "long", "lr", "short"
    ]
    for termo in termos_para_remover:
        limpo = limpo.replace(termo, "")
    return limpo


@vendas_bp.route("/api/cliente/<int:cliente_id>/armas")
@login_required
def api_armas_cliente(cliente_id):
    """
    Retorna as armas do cliente, opcionalmente filtradas por calibre.
    """
    calibre_alvo = request.args.get("calibre")
    todas_armas = Arma.query.filter_by(cliente_id=cliente_id).all()
    
    armas_filtradas = []
    
    if calibre_alvo:
        alvo_limpo = normalizar_calibre(calibre_alvo)
        
        # Tabela de equivalência para aumentar a chance de match
        equivalencias = {
            "9": ["9x19", "9", "380"],
            "9x19": ["9", "9x19"],
            "38": ["38", "357"],
            "357": ["357"],
            "380": ["380"],
            "12": ["12"],
            "22": ["22"],
            "40": ["40", "40sw"],
            "45": ["45", "45acp"]
        }
        compativeis = equivalencias.get(alvo_limpo, [alvo_limpo])

        for arma in todas_armas:
            arma_calibre_limpo = normalizar_calibre(arma.calibre)
            
            match = False
            if alvo_limpo == "38" and "357" in arma_calibre_limpo:
                match = True
            else:
                for c in compativeis:
                    if c == arma_calibre_limpo or c in arma_calibre_limpo or arma_calibre_limpo in c:
                        match = True
                        break
            
            if match:
                armas_filtradas.append(arma)
    else:
        armas_filtradas = todas_armas

    return jsonify([{
        "id": a.id,
        "descricao": f"{a.tipo or 'Arma'} {a.marca or ''} {a.modelo or ''}",
        "serial": a.numero_serie,
        "calibre": a.calibre,
        # CORREÇÃO DO ERRO: Removemos a.sinarm e usamos 'emissor_craf' ou 'numero_sigma'
        "sistema": f"{a.emissor_craf or a.numero_sigma or 'S/N'}" 
    } for a in armas_filtradas])


@vendas_bp.route("/api/produto/<int:produto_id>/detalhes")
@login_required
def api_produto_detalhes(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    return jsonify({
        "id": produto.id,
        "nome": produto.nome,
        "preco": float(produto.preco_a_vista or 0),
        "estoque": 10, # Placeholder
        "tipo": (produto.tipo_rel.nome if produto.tipo_rel else "").lower(),
        "categoria": (produto.categoria.nome if produto.categoria else "").lower(),
        "calibre": (produto.calibre_rel.nome if produto.calibre_rel else "")
    })


@vendas_bp.route("/api/produtos")
@login_required
def api_buscar_produtos():
    termo = request.args.get("q", "")
    produtos = Produto.query.filter(
        (Produto.nome.ilike(f"%{termo}%")) | 
        (Produto.codigo.ilike(f"%{termo}%"))
    ).limit(10).all()
    
    return jsonify([{
        "id": p.id,
        "nome": p.nome,
        "preco": float(p.preco_a_vista or 0),
        "estoque": 10 # Placeholder
    } for p in produtos])


@vendas_bp.route("/api/estoque/<int:produto_id>")
@login_required
def api_buscar_estoque_produto(produto_id):
    itens = ItemEstoque.query.filter_by(
        produto_id=produto_id, 
        status="disponivel"
    ).all()
    
    return jsonify([{
        "id": i.id,
        "serial": i.numero_serie,
        "lote": i.lote,
        "embalagem": i.numero_embalagem 
    } for i in itens])