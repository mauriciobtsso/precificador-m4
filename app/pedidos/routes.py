from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime
from app.extensions import db
from app.models import PedidoCompra, ItemPedido
from app.clientes.models import Cliente
from app.utils.number_helpers import parse_brl, parse_pct
from app.pedidos import pedidos_bp
from sqlalchemy import func


# ---------------------------------------------------
# NOVO PEDIDO
# ---------------------------------------------------
@pedidos_bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo_pedido():
    if request.method == "POST":
        fornecedor_id = request.form.get("fornecedor")
        cond_pagto = request.form.get("cond_pagto")
        modo = request.form.get("modo_desconto")

        perc_armas = parse_pct(request.form.get("percentual_armas"))
        perc_municoes = parse_pct(request.form.get("percentual_municoes"))
        perc_unico = parse_pct(request.form.get("percentual_unico"))

        numero = datetime.now().strftime("%Y%m%d%H%M%S")

        pedido = PedidoCompra(
            numero=numero,
            data_pedido=datetime.now().date(),
            cond_pagto=cond_pagto,
            modo_desconto=modo,
            percentual_armas=perc_armas,
            percentual_municoes=perc_municoes,
            percentual_unico=perc_unico,
            fornecedor_id=int(fornecedor_id) if fornecedor_id else None,
        )
        db.session.add(pedido)
        db.session.flush()

        codigos = request.form.getlist("codigo[]")
        descricoes = request.form.getlist("descricao[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        for codigo, desc, qtd, val in zip(codigos, descricoes, quantidades, valores):
            desc = (desc or "").strip()
            if not desc:
                continue
            q = int(qtd or 0)
            v = parse_brl(val)
            if q <= 0 or v <= 0:
                continue
            item = ItemPedido(
                pedido_id=pedido.id,
                codigo=codigo,
                descricao=desc,
                quantidade=q,
                valor_unitario=v,
            )
            db.session.add(item)

        db.session.commit()
        flash("Pedido criado com sucesso!", "success")
        return redirect(url_for("pedidos.listar_pedidos"))

    fornecedores = [
        c for c in Cliente.query.all()
        if getattr(c, "documento", None) and "/" in c.documento
    ]
    return render_template("pedidos/novo.html", fornecedores=fornecedores)


# ---------------------------------------------------
# EDITAR PEDIDO
# ---------------------------------------------------
@pedidos_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)

    if request.method == "POST":
        pedido.cond_pagto = request.form.get("cond_pagto")
        pedido.modo_desconto = request.form.get("modo_desconto")
        pedido.percentual_armas = float(request.form.get("percentual_armas") or 0)
        pedido.percentual_municoes = float(request.form.get("percentual_municoes") or 0)
        pedido.percentual_unico = float(request.form.get("percentual_unico") or 0)

        for it in list(pedido.itens):
            db.session.delete(it)

        codigos = request.form.getlist("codigo[]")
        descricoes = request.form.getlist("descricao[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        for codigo, desc, qtd, val in zip(codigos, descricoes, quantidades, valores):
            if not desc.strip():
                continue
            q = int(qtd or 0)
            v = parse_brl(val)
            if q <= 0 or v <= 0:
                continue
            item = ItemPedido(
                pedido_id=pedido.id,
                codigo=codigo,
                descricao=desc.strip(),
                quantidade=q,
                valor_unitario=v,
            )
            db.session.add(item)

        db.session.commit()
        flash("Pedido atualizado com sucesso!", "success")
        return redirect(url_for("pedidos.listar_pedidos"))

    fornecedores = Cliente.query.all()
    return render_template("pedidos/novo.html", pedido=pedido, fornecedores=fornecedores)


# ---------------------------------------------------
# LISTAR PEDIDOS
# ---------------------------------------------------
@pedidos_bp.route("/")
@login_required
def listar_pedidos():
    query = PedidoCompra.query.join(PedidoCompra.fornecedor)

    numero = request.args.get("numero", "").strip()
    fornecedor_nome = request.args.get("fornecedor", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    valor_min = request.args.get("valor_min", "").strip()
    valor_max = request.args.get("valor_max", "").strip()

    if numero:
        query = query.filter(PedidoCompra.numero.ilike(f"%{numero}%"))
    if fornecedor_nome:
        query = query.filter(Cliente.nome.ilike(f"%{fornecedor_nome}%"))

    if data_inicio:
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            query = query.filter(PedidoCompra.data_pedido >= di)
        except ValueError:
            flash("Data inicial inválida.", "warning")
    if data_fim:
        try:
            df = datetime.strptime(data_fim, "%Y-%m-%d").date()
            query = query.filter(PedidoCompra.data_pedido <= df)
        except ValueError:
            flash("Data final inválida.", "warning")

    if valor_min or valor_max:
        subq = (
            db.session.query(
                ItemPedido.pedido_id,
                func.sum(ItemPedido.quantidade * ItemPedido.valor_unitario).label("valor_total")
            )
            .group_by(ItemPedido.pedido_id)
            .subquery()
        )
        query = query.join(subq, subq.c.pedido_id == PedidoCompra.id)

        if valor_min:
            try:
                query = query.filter(subq.c.valor_total >= float(valor_min))
            except ValueError:
                flash("Valor mínimo inválido.", "warning")
        if valor_max:
            try:
                query = query.filter(subq.c.valor_total <= float(valor_max))
            except ValueError:
                flash("Valor máximo inválido.", "warning")

    pedidos = query.all()
    return render_template("pedidos/listar.html", pedidos=pedidos)


# ---------------------------------------------------
# EXCLUIR PEDIDO
# ---------------------------------------------------
@pedidos_bp.route("/<int:id>/excluir", methods=["POST", "GET"])
@login_required
def excluir_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)
    db.session.delete(pedido)
    db.session.commit()
    flash("Pedido excluído com sucesso!", "success")
    return redirect(url_for("pedidos.listar_pedidos"))
