# ============================================================
# MÓDULO: PRODUTOS — API JSON (Busca e Autocomplete)
# Arquivo: app/produtos/routes/api.py
# ============================================================

from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from app.produtos import produtos_bp
from app.produtos.models import Produto, MarcaProduto

@produtos_bp.route("/api/buscar", methods=["GET"])
@login_required
def api_buscar_produtos():
    """
    Retorna lista de produtos do catálogo para Select2/Autocomplete.
    Busca por Nome, Código (SKU) ou Marca.
    """
    termo = request.args.get("termo", "").strip()
    
    # Otimização: Carrega a marca junto para evitar múltiplas consultas (N+1)
    # Joinedload é vital para performance em listas
    query = Produto.query.options(joinedload(Produto.marca_rel))

    if termo:
        # Filtra por Nome do Produto, Código OU Nome da Marca
        query = query.outerjoin(MarcaProduto).filter(
            or_(
                Produto.nome.ilike(f"%{termo}%"),
                Produto.codigo.ilike(f"%{termo}%"),
                MarcaProduto.nome.ilike(f"%{termo}%")
            )
        )
    
    # Limita a 50 resultados para não pesar no navegador
    produtos = query.order_by(Produto.nome).limit(50).all()
    
    # Formata para o padrão que o Select2 espera
    resultado = [
        {
            "id": p.id,
            "text": f"{p.nome} ({p.codigo or 'S/C'})", # Campo 'text' é o que aparece na lista
            "marca": p.marca_rel.nome if p.marca_rel else "",
            "codigo": p.codigo or ""
        }
        for p in produtos
    ]
    
    return jsonify(resultado)