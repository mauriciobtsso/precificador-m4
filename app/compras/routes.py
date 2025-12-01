# ============================================================
# MÓDULO: COMPRAS — Rotas (Auto-Link + GT Única)
# ============================================================

from flask import render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required
from app import db
from app.compras import compras_nf_bp
from app.compras.utils import parse_nf_xml_inteligente
from app.compras.models import CompraNF, CompraItem
from app.models import PedidoCompra
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from app.clientes.models import Cliente
from datetime import datetime
from decimal import Decimal
import uuid
import json
from sqlalchemy import desc
from app.utils.r2_helpers import upload_fileobj_r2

def _parse_dt_flex(dt_str):
    if not dt_str: return None
    try: return datetime.fromisoformat(str(dt_str).strip().replace("Z", "+00:00"))
    except: return datetime.now()

@compras_nf_bp.route("/", endpoint="index")
@login_required
def index():
    nfs = CompraNF.query.order_by(desc(CompraNF.criado_em)).all()
    return render_template("compras/index.html", nfs=nfs)

@compras_nf_bp.route("/importar", methods=["GET", "POST"])
@login_required
def importar():
    if request.method == "POST":
        file = request.files.get("xml")
        if not file: return jsonify(success=False, message="Sem arquivo"), 400
        return jsonify(parse_nf_xml_inteligente(file))
    
    pedidos = PedidoCompra.query.filter(
        PedidoCompra.status.in_(['Aguardando', 'Confirmado', 'Aguardando NF'])
    ).order_by(PedidoCompra.id.desc()).all()
    return render_template("compras/importar.html", pedidos_abertos=pedidos)

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

        nf = CompraNF(
            fornecedor=data.get("fornecedor"),
            cnpj_fornecedor=data.get("cnpj_emit"),
            numero=data.get("numero"),
            chave=chave or str(uuid.uuid4()),
            data_emissao=_parse_dt_flex(data.get("data_emissao")),
            valor_total=Decimal(str(data.get("valor_total") or 0)),
            pedido_id=int(data.get("pedido_id")) if data.get("pedido_id") else None
        )

        for it in itens:
            # === AUTO-LINK INTELIGENTE ===
            cProd = str(it.get("codigo_xml") or "").strip()
            produto_match = None
            if cProd:
                # 1. Código Exato
                produto_match = Produto.query.filter_by(codigo=cProd).first()
                # 2. Código sem zeros (Ex: 00123 -> 123)
                if not produto_match:
                    cProd_clean = cProd.lstrip("0")
                    if cProd_clean: produto_match = Produto.query.filter_by(codigo=cProd_clean).first()

            nf.itens.append(CompraItem(
                descricao=it.get("descricao"),
                codigo_produto_xml=cProd,
                marca=it.get("marca"),
                modelo=it.get("modelo"),
                calibre=it.get("calibre"),
                lote=it.get("lote"),
                numero_embalagem=it.get("embalagem"), # Vem do parser
                seriais_xml=it.get("seriais_xml"), 
                quantidade=Decimal(str(it.get("quantidade") or 0)),
                valor_unitario=Decimal(str(it.get("valor_unitario") or 0)),
                valor_total=Decimal(str(it.get("valor_total") or 0)),
                produto_id=produto_match.id if produto_match else None
            ))

        if nf.pedido:
            nf.pedido.status = "Em Transito"
            db.session.add(nf.pedido)

        db.session.add(nf)
        db.session.commit()
        return jsonify(success=True, nf_id=nf.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

# === UPLOAD DE GUIA ÚNICA ===
@compras_nf_bp.route("/upload_guia_nf/<int:nf_id>", methods=["POST"])
@login_required
def upload_guia_nf(nf_id):
    nf = CompraNF.query.get_or_404(nf_id)
    file = request.files.get("guia_file")
    selo = request.form.get("numero_selo")
    
    if file:
        url = upload_fileobj_r2(file, "guias_transito")
        if url: nf.guia_transito_file = url
    
    if selo: nf.numero_selo = selo
    
    db.session.commit()
    return redirect(url_for('compras_nf.view', nf_id=nf.id))

@compras_nf_bp.route("/receber_item", methods=["POST"])
@login_required
def receber_item():
    try:
        compra_item_id = request.form.get("compra_item_id")
        produto_id = request.form.get("produto_id")
        tipo_item = request.form.get("tipo_item") # "arma" ou "municao"
        
        c_item = CompraItem.query.get_or_404(compra_item_id)
        produto = Produto.query.get_or_404(produto_id)
        nf = c_item.nf

        if c_item.itens_gerados_estoque.count() > 0:
            return jsonify(success=False, message="Item já recebido"), 400

        # Usa Guia Global da NF
        guia_url = nf.guia_transito_file
        numero_selo = nf.numero_selo

        # Fornecedor
        fornecedor_id = None
        if nf.pedido and nf.pedido.fornecedor_id:
            fornecedor_id = nf.pedido.fornecedor_id
        elif nf.cnpj_fornecedor:
            clean = ''.join(filter(str.isdigit, nf.cnpj_fornecedor))
            cli = Cliente.query.filter((Cliente.documento == nf.cnpj_fornecedor) | (Cliente.documento == clean)).first()
            if cli: fornecedor_id = cli.id

        qtd_total = int(c_item.quantidade)

        if tipo_item == 'arma':
            import json
            try: serials = json.loads(request.form.get("serials"))
            except: serials = []
            
            for i in range(qtd_total):
                serial = serials[i] if i < len(serials) else None
                db.session.add(ItemEstoque(
                    produto_id=produto.id,
                    fornecedor_id=fornecedor_id,
                    compra_item_id=c_item.id,
                    tipo_item="arma",
                    numero_serie=serial,
                    lote=c_item.lote, # Se tiver no XML, usa. Se não, vazio.
                    nota_fiscal=nf.numero,
                    data_nf=nf.data_emissao.date() if nf.data_emissao else None,
                    status="disponivel",
                    quantidade=1,
                    observacoes=f"Entrada via NF {nf.numero}",
                    guia_transito_file=guia_url,
                    numero_selo=numero_selo
                ))
        else:
            # MUNIÇÃO: Entrada "Grosso"
            db.session.add(ItemEstoque(
                produto_id=produto.id,
                fornecedor_id=fornecedor_id,
                compra_item_id=c_item.id,
                tipo_item="municao",
                numero_serie=None,
                lote=c_item.lote, # Salva lote do XML se tiver, mas não obriga
                nota_fiscal=nf.numero,
                data_nf=nf.data_emissao.date() if nf.data_emissao else None,
                status="disponivel",
                quantidade=qtd_total, # Salva o total (ex: 1000)
                observacoes=f"Entrada Atacado via NF {nf.numero}",
                guia_transito_file=guia_url,
                numero_selo=numero_selo,
                numero_embalagem=None # Deixa para definir no Estoque
            ))

        if nf.pedido:
            nf.pedido.status = "Recebido"
            db.session.add(nf.pedido)

        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

# (Rotas de view, delete, edit, desfazer mantidas igual ao anterior)
@compras_nf_bp.route("/desfazer_recebimento", methods=["POST"])
@login_required
def desfazer_recebimento():
    try:
        data = request.get_json()
        itens = ItemEstoque.query.filter_by(compra_item_id=data.get('compra_item_id')).all()
        if not itens: return jsonify(success=False, message="Nada a desfazer"), 400
        for item in itens:
            if item.status != 'disponivel': return jsonify(success=False, message="Movimentado"), 400
            db.session.delete(item)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@compras_nf_bp.route("/<int:nf_id>", endpoint="view")
@login_required
def view_nf(nf_id):
    nf = CompraNF.query.get_or_404(nf_id)
    return render_template("compras/view.html", nf=nf)

@compras_nf_bp.route("/<int:nf_id>/editar", methods=["GET", "POST"], endpoint="edit")
@login_required
def edit_nf(nf_id):
    return redirect(url_for('compras_nf.view', nf_id=nf_id))

@compras_nf_bp.route("/<int:nf_id>/excluir", methods=["GET", "POST"], endpoint="delete")
@login_required
def delete_nf(nf_id):
    nf = CompraNF.query.get_or_404(nf_id)
    db.session.delete(nf)
    db.session.commit()
    return redirect(url_for('compras_nf.index'))