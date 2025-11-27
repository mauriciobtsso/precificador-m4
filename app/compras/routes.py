# ============================================================
# MÓDULO: COMPRAS — Rotas principais (com parser híbrido LLM e Estoque)
# ============================================================

from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from app import db
from app.compras import compras_nf_bp
from app.compras.utils import parse_nf_xml_inteligente
from app.compras.models import CompraNF, CompraItem
from app.models import PedidoCompra
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from datetime import datetime
from decimal import Decimal
import uuid
from sqlalchemy import desc


def _parse_dt_flex(dt_str: str):
    """Aceita 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS', com/sem timezone, e '...Z'."""
    if not dt_str:
        return None
    s = dt_str.strip()
    try:
        # Normaliza 'Z'
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        # fromisoformat aceita timezone no formato ±HH:MM
        return datetime.fromisoformat(s)
    except Exception:
        try:
            # Tenta só data (dEmi)
            return datetime.fromisoformat(s + "T00:00:00")
        except Exception:
            return None


# ============================================================
# LISTAGEM DE NF DE COMPRAS
# ============================================================
@compras_nf_bp.route("/", endpoint="index")
@login_required
def index():
    """Lista todas as NFs de compra registradas"""
    nfs = CompraNF.query.order_by(desc(CompraNF.criado_em)).all()
    return render_template("compras/index.html", nfs=nfs)


# ============================================================
# IMPORTAR — Upload + Parser Híbrido XML
# ============================================================
@compras_nf_bp.route("/importar", methods=["GET", "POST"])
@login_required
def importar():
    if request.method == "POST":
        file = request.files.get("xml")
        if not file: return jsonify(success=False, message="Sem arquivo"), 400
        res = parse_nf_xml_inteligente(file)
        return jsonify(res)
    
    pedidos = PedidoCompra.query.filter(
        PedidoCompra.status.in_(['Aguardando', 'Confirmado', 'Aguardando NF'])
    ).order_by(PedidoCompra.id.desc()).all()
    return render_template("compras/importar.html", pedidos_abertos=pedidos)

# ============================================================
# SALVAR NF E ITENS NO BANCO — com validação de duplicidade
# ============================================================
@compras_nf_bp.route("/salvar", methods=["POST"])
@login_required
def salvar_nf():
    try:
        data = request.get_json(force=True)
        itens = data.get("itens") or []
        if not itens: return jsonify(success=False, message="Sem itens"), 400

        chave = (data.get("chave") or "").strip()
        if chave and CompraNF.query.filter_by(chave=chave).first():
            return jsonify(success=False, message="NF já cadastrada"), 409

        data_emissao_str = data.get("data_emissao")
        dt = _parse_dt_flex(data_emissao_str)

        # Valor total com fallback
        v_total = data.get("valor_total", data.get("valor_total_nf"))
        v_total = Decimal(str(v_total or 0))

        nf = CompraNF(
            fornecedor=data.get("fornecedor"),
            numero=data.get("numero"),
            chave=chave or str(uuid.uuid4()),
            data_emissao=dt or datetime.now(),
            valor_total=v_total,
            pedido_id=int(data.get("pedido_id")) if data.get("pedido_id") else None
        )

        for it in itens:
            nf.itens.append(CompraItem(
                descricao=it.get("descricao"),
                marca=it.get("marca"),
                modelo=it.get("modelo"),
                calibre=it.get("calibre"),
                lote=it.get("lote") or it.get("numero_serie"),
                seriais_xml=it.get("seriais_xml"),
                quantidade=Decimal(str(it.get("quantidade") or 0)),
                valor_unitario=Decimal(str(it.get("valor_unitario") or 0)),
                valor_total=Decimal(str(it.get("valor_total") or 0))
            ))

        if nf.pedido_id:
            ped = PedidoCompra.query.get(nf.pedido_id)
            if ped: ped.status = "Em Transito"

        db.session.add(nf)
        db.session.commit()
        return jsonify(success=True, nf_id=nf.id)
    
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

# ============================================================
# RECEBER ITEM (Gera Estoque) — Nova Rota
# ============================================================
@compras_nf_bp.route("/receber_item", methods=["POST"])
@login_required
def receber_item():
    try:
        data = request.get_json(force=True)
        c_item = CompraItem.query.get_or_404(data.get("compra_item_id"))
        produto = Produto.query.get_or_404(data.get("produto_id"))
        serials = data.get("serials") or []

        if c_item.itens_gerados_estoque.count() > 0:
            return jsonify(success=False, message="Item já recebido"), 400

        qtd = int(c_item.quantidade)
        nf = c_item.nf

        for i in range(qtd):
            serial = serials[i] if i < len(serials) else None
            
            # Cria item no estoque
            novo = ItemEstoque(
                produto_id=produto.id,
                compra_item_id=c_item.id,
                tipo_item="arma", # Lógica futura: pegar do produto.tipo
                numero_serie=serial,
                lote=c_item.lote,
                nota_fiscal=nf.numero,
                data_nf=nf.data_emissao.date() if nf.data_emissao else None,
                status="disponivel",
                quantidade=1,
                observacoes=f"Recebido via NF {nf.numero}"
            )
            db.session.add(novo)
        
        # Se o pedido estava em trânsito e tudo foi recebido, poderia mudar para Recebido (opcional)
        
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

# ============================================================
# VISUALIZAR NF (Detalhes)
# ============================================================
@compras_nf_bp.route("/<int:nf_id>", endpoint="view")
@login_required
def view_nf(nf_id):
    nf = CompraNF.query.get_or_404(nf_id)
    return render_template("compras/view.html", nf=nf)

# ============================================================
# EXCLUIR NF
# ============================================================
@compras_nf_bp.route("/<int:nf_id>/excluir", methods=["GET", "POST"], endpoint="delete")
@login_required
def delete_nf(nf_id):
    nf = CompraNF.query.get_or_404(nf_id)
    db.session.delete(nf)
    db.session.commit()
    return redirect(url_for('compras_nf.index'))

# ============================================================
# EDITAR NF (Redireciona para Mesa de Recebimento)
# ============================================================
@compras_nf_bp.route("/<int:nf_id>/editar", methods=["GET", "POST"], endpoint="edit")
@login_required
def edit_nf(nf_id):
    return redirect(url_for('compras_nf.view', nf_id=nf_id))