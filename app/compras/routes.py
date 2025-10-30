# ============================================================
# MÓDULO: COMPRAS — Rotas principais (com parser híbrido LLM)
# ============================================================

from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from app import db
from app.compras import compras_nf_bp
from app.compras.utils import parse_nf_xml_inteligente
from app.compras.models import CompraNF, CompraItem
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
    """Tela para importar e processar XML de NF de entrada"""
    if request.method == "POST":
        file = request.files.get("xml")
        if not file:
            return jsonify(success=False, message="Nenhum arquivo enviado."), 400

        resultado = parse_nf_xml_inteligente(file)
        if not resultado.get("success"):
            return jsonify(success=False, message=f"Erro ao processar XML: {resultado.get('error')}"), 500

        # Já retorna o JSON do parser, que inclui valor_total, fornecedor e chave
        return jsonify(resultado)

    return render_template("compras/importar.html")


# ============================================================
# SALVAR NF E ITENS NO BANCO — com validação de duplicidade
# ============================================================
@compras_nf_bp.route("/salvar", methods=["POST"])
@login_required
def salvar_nf():
    """
    Recebe JSON com os itens importados e grava a NF e seus itens no banco.
    Valida duplicidade pela chave da NF.
    """
    try:
        data = request.get_json(force=True)
        itens = data.get("itens") or []
        if not itens:
            return jsonify(success=False, message="Nenhum item recebido."), 400

        # Dados básicos da NF
        chave = (data.get("chave") or "").strip()
        numero = (data.get("numero") or "").strip()
        fornecedor = data.get("fornecedor", "Fornecedor não informado")
        cnpj_emit = (data.get("cnpj_emit") or "").strip()

        data_emissao_str = data.get("data_emissao")
        dt = _parse_dt_flex(data_emissao_str)
        data_emissao = dt if dt else datetime.utcnow()

        # Aceita 'valor_total' (novo) ou 'valor_total_nf' (legado)
        valor_total_in = data.get("valor_total", data.get("valor_total_nf"))
        try:
            valor_total_nf = Decimal(str(valor_total_in)) if valor_total_in is not None else Decimal(0)
        except Exception:
            valor_total_nf = Decimal(0)

        # ✅ Verifica duplicidade por chave (se existir)
        if chave:
            nf_existente = CompraNF.query.filter_by(chave=chave).first()
            if nf_existente:
                return jsonify(
                    success=False,
                    message=f"NF já cadastrada anteriormente (chave: {chave}).",
                    nf_id=nf_existente.id,
                ), 409

        # Criação da NF — gera UUID SOMENTE se não houver chave real
        nf = CompraNF(
            fornecedor=fornecedor,
            numero=numero,
            chave=chave or str(uuid.uuid4()),
            data_emissao=data_emissao,
            valor_total=valor_total_nf
        )

        # Criação dos itens
        for it in itens:
            quantidade = Decimal(str(it.get("quantidade") or 0))
            valor_unitario = Decimal(str(it.get("valor_unitario") or 0))
            item = CompraItem(
                descricao=it.get("descricao"),
                marca=it.get("marca"),
                modelo=it.get("modelo"),
                calibre=it.get("calibre"),
                lote=it.get("lote") or it.get("numero_serie"),
                quantidade=quantidade,
                valor_unitario=valor_unitario,
            )
            item.valor_total = item.quantidade * item.valor_unitario
            nf.itens.append(item)

        db.session.add(nf)
        db.session.commit()

        return jsonify(success=True, message="NF salva com sucesso.", nf_id=nf.id)
    
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=f"Erro ao salvar NF: {e}"), 500
    
    
# ============================================================
# VISUALIZAR NF (Detalhes)
# ============================================================
@compras_nf_bp.route("/<int:nf_id>", endpoint="view")
@login_required
def view_nf(nf_id):
    """Visualiza os detalhes de uma NF."""
    nf = CompraNF.query.get_or_404(nf_id)
    return render_template("compras/view.html", nf=nf)


# ============================================================
# EXCLUIR NF
# ============================================================
@compras_nf_bp.route("/<int:nf_id>/excluir", methods=["GET", "POST"], endpoint="delete")
@login_required
def delete_nf(nf_id):
    """Exclui uma NF e seus itens."""
    nf = CompraNF.query.get_or_404(nf_id)
    try:
        db.session.delete(nf)
        db.session.commit()
        return redirect(url_for('compras_nf.index'))
    except Exception as e:
        db.session.rollback()
        return f"Erro ao excluir NF: {e}", 500


# ============================================================
# EDITAR NF (Placeholder)
# ============================================================
@compras_nf_bp.route("/<int:nf_id>/editar", methods=["GET", "POST"], endpoint="edit")
@login_required
def edit_nf(nf_id):
    """Placeholder para edição de NF."""
    nf = CompraNF.query.get_or_404(nf_id)
    return f"Tela de Edição da NF {nf.numero or nf.chave}", 200
