from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_
from app import db
from app.estoque import estoque_bp
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto, MarcaProduto
from app.clientes.models import Cliente
from app.vendas.models import ItemVenda, Venda
from app.utils.datetime import now_local
from datetime import datetime

# ================================
# LISTAGEM — ARMAS (COFRE)
# ================================
@estoque_bp.route("/armas")
@login_required
def armas_listar():
    # Parâmetros de Busca
    termo = request.args.get('termo', '').strip()
    filtro_status = request.args.get('status', '').strip()

    query = ItemEstoque.query.options(
        joinedload(ItemEstoque.produto).joinedload(Produto.marca_rel),
        joinedload(ItemEstoque.fornecedor),
        joinedload(ItemEstoque.venda_item).joinedload(ItemVenda.venda).joinedload(Venda.cliente)
    ).filter_by(tipo_item="arma")

    # Filtro Inteligente (Serial, Nome Produto, Marca)
    if termo:
        like_termo = f"%{termo}%"
        query = query.join(ItemEstoque.produto).outerjoin(MarcaProduto, Produto.marca_id == MarcaProduto.id).filter(
            or_(
                ItemEstoque.numero_serie.ilike(like_termo),
                Produto.nome.ilike(like_termo),
                MarcaProduto.nome.ilike(like_termo),
                ItemEstoque.nota_fiscal.ilike(like_termo)
            )
        )

    if filtro_status:
        query = query.filter(ItemEstoque.status == filtro_status)

    # Ordenação: Disponíveis primeiro, depois por data
    itens = query.order_by(ItemEstoque.status.asc(), ItemEstoque.data_entrada.desc()).all()

    # Cálculo dos Totais (Mantém a lógica rápida)
    resumo = db.session.query(
        ItemEstoque.status, func.count(ItemEstoque.id)
    ).filter_by(tipo_item="arma").group_by(ItemEstoque.status).all()

    contagem = {status: qtd for status, qtd in resumo}
    
    totais = {
        "total": sum(contagem.values()),
        "disponivel": contagem.get("disponivel", 0),
        "reservada": contagem.get("reservada", 0),
        "vendida": contagem.get("vendida", 0) + contagem.get("entregue", 0),
        "manutencao": contagem.get("manutencao", 0)
    }

    return render_template("estoque/armas/listar.html", itens=itens, totais=totais, termo=termo, filtro_status=filtro_status)

# ================================
# NOVA / EDITAR — ARMA
# ================================
@estoque_bp.route("/armas/novo", methods=["GET", "POST"])
@estoque_bp.route("/armas/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def armas_gerenciar(item_id=None):
    item = None
    if item_id:
        item = ItemEstoque.query.get_or_404(item_id)
    
    if request.method == "POST":
        try:
            produto_id = request.form.get("produto_id")
            fornecedor_id = request.form.get("fornecedor_id")
            numero_serie = request.form.get("numero_serie")
            nota_fiscal = request.form.get("nota_fiscal")
            status = request.form.get("status")
            obs = request.form.get("observacoes")
            
            # Tratamento de Datas
            dt_ent_str = request.form.get("data_entrada")
            dt_nf_str = request.form.get("data_nf")
            
            data_entrada = datetime.strptime(dt_ent_str, "%Y-%m-%d").date() if dt_ent_str else now_local().date()
            data_nf = datetime.strptime(dt_nf_str, "%Y-%m-%d").date() if dt_nf_str else None

            if not item:
                item = ItemEstoque(tipo_item="arma")
                db.session.add(item)
                flash("✅ Arma adicionada ao cofre!", "success")
            else:
                flash("✅ Dados da arma atualizados!", "info")

            item.produto_id = produto_id
            item.fornecedor_id = fornecedor_id if fornecedor_id else None
            item.numero_serie = numero_serie
            item.nota_fiscal = nota_fiscal
            item.data_nf = data_nf  # Novo campo
            item.status = status
            item.data_entrada = data_entrada
            item.observacoes = obs

            db.session.commit()
            return redirect(url_for("estoque.armas_listar"))

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Erro ao salvar: {e}", "danger")

    produtos = Produto.query.order_by(Produto.nome).all()
    
    # Filtra Fornecedores: Apenas CNPJ (length > 11 chars limpos, geralmente 14) ou flag específica se tiver
    # Aqui assumo que PJ tem documento maior que 11 dígitos
    todos_clientes = Cliente.query.order_by(Cliente.nome).all()
    fornecedores = [c for c in todos_clientes if c.documento and len(c.documento.replace('.','').replace('-','').replace('/','')) > 11]

    return render_template(
        "estoque/armas/form.html",
        item=item,
        produtos=produtos,
        fornecedores=fornecedores,
        tipo_item="arma",
        hoje=now_local().strftime("%Y-%m-%d")
    )

# ... (Mantenha as rotas de Detalhe e Excluir inalteradas ou copie do anterior se preferir)
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
    if item.status == 'vendido':
        flash("⚠️ Arma vendida não pode ser excluída.", "warning")
        return redirect(url_for("estoque.armas_listar"))
    try:
        db.session.delete(item)
        db.session.commit()
        flash("🗑️ Arma removida do cofre.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Erro ao excluir.", "danger")
    return redirect(url_for("estoque.armas_listar"))