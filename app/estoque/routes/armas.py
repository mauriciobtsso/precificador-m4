from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from app import db
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from app.clientes.models import Cliente
from app.vendas.models import ItemVenda
from app.utils.datetime import now_local
from app.utils.r2_helpers import upload_fileobj_r2, gerar_link_r2 # Import necessário
from datetime import datetime

@estoque_bp.route("/armas")
@login_required
def armas_listar():
    # Busca com termo de pesquisa
    termo = request.args.get("termo", "").strip()
    status_filtro = request.args.get("status", "").strip()

    query = ItemEstoque.query.options(
        joinedload(ItemEstoque.produto),
        joinedload(ItemEstoque.fornecedor),
        joinedload(ItemEstoque.venda_item)
    ).filter_by(tipo_item="arma")

    if termo:
        query = query.join(ItemEstoque.produto).filter(
            (ItemEstoque.numero_serie.ilike(f"%{termo}%")) | 
            (Produto.nome.ilike(f"%{termo}%")) |
            (ItemEstoque.nota_fiscal.ilike(f"%{termo}%"))
        )
    
    if status_filtro:
        query = query.filter(ItemEstoque.status == status_filtro)

    itens = query.order_by(ItemEstoque.data_entrada.desc()).all()

    # Totais
    resumo = db.session.query(ItemEstoque.status, func.count(ItemEstoque.id)).filter_by(tipo_item="arma").group_by(ItemEstoque.status).all()
    contagem = {status: qtd for status, qtd in resumo}
    totais = {
        "total": sum(contagem.values()),
        "disponivel": contagem.get("disponivel", 0),
        "reservada": contagem.get("reservada", 0),
        "vendida": contagem.get("vendida", 0) + contagem.get("entregue", 0),
        "manutencao": contagem.get("manutencao", 0)
    }

    return render_template("estoque/armas/listar.html", itens=itens, totais=totais, termo=termo, filtro_status=status_filtro)

# === NOVA ROTA: VISUALIZAR GUIA (RESOLVE O 404) ===
@estoque_bp.route("/armas/<int:item_id>/guia")
@login_required
def visualizar_guia(item_id):
    item = ItemEstoque.query.get_or_404(item_id)
    
    if not item.guia_transito_file:
        return "Guia não anexada.", 404

    # Se já for um link completo (http...), redireciona direto
    if item.guia_transito_file.startswith("http"):
        return redirect(item.guia_transito_file)

    # Se for caminho relativo, gera link assinado no R2
    url_assinada = gerar_link_r2(item.guia_transito_file)
    if url_assinada:
        return redirect(url_assinada)
    
    return "Erro ao gerar link do arquivo.", 500

@estoque_bp.route("/armas/novo", methods=["GET", "POST"])
@estoque_bp.route("/armas/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def armas_gerenciar(item_id=None):
    item = None
    if item_id:
        item = ItemEstoque.query.get_or_404(item_id)
    
    if request.method == "POST":
        try:
            if not item:
                item = ItemEstoque(tipo_item="arma")
                db.session.add(item)

            item.produto_id = request.form.get("produto_id")
            item.fornecedor_id = request.form.get("fornecedor_id") or None
            item.numero_serie = request.form.get("numero_serie")
            item.nota_fiscal = request.form.get("nota_fiscal")
            item.status = request.form.get("status")
            item.observacoes = request.form.get("observacoes")
            
            # Selo e Datas
            item.numero_selo = request.form.get("numero_selo")
            
            dt_ent = request.form.get("data_entrada")
            dt_nf = request.form.get("data_nf")
            
            if dt_ent: item.data_entrada = datetime.strptime(dt_ent, "%Y-%m-%d").date()
            if dt_nf: item.data_nf = datetime.strptime(dt_nf, "%Y-%m-%d").date()

            # Upload da Guia (Se enviado na edição)
            guia = request.files.get("guia_file")
            if guia:
                url = upload_fileobj_r2(guia, "guias_transito")
                if url: item.guia_transito_file = url

            db.session.commit()
            flash("Salvo com sucesso!", "success")
            return redirect(url_for("estoque.armas_listar"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")

    produtos = Produto.query.order_by(Produto.nome).all()
    fornecedores = Cliente.query.order_by(Cliente.nome).all() # Traz todos para permitir correção manual
    
    return render_template(
        "estoque/armas/form.html", 
        item=item, 
        produtos=produtos, 
        fornecedores=fornecedores, 
        hoje=now_local().strftime("%Y-%m-%d")
    )

# (Rotas detalhe e excluir mantidas)
@estoque_bp.route("/armas/<int:item_id>/detalhe")
@login_required
def armas_detalhe(item_id):
    item = ItemEstoque.query.get_or_404(item_id)
    venda_item = ItemVenda.query.filter_by(item_estoque_id=item.id).first()
    return render_template("estoque/armas/modal_detalhe.html", item=item, venda_item=venda_item)

@estoque_bp.route("/armas/<int:item_id>/excluir", methods=["POST"])
@login_required
def armas_excluir(item_id):
    item = ItemEstoque.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("estoque.armas_listar"))