# ============================================================
# MÓDULO: PRODUTOS — API JSON (Busca e Autocomplete)
# Arquivo: app/produtos/routes/api.py
# ============================================================

from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from app.produtos import produtos_bp
# Importação segura dos modelos
from app.produtos.models import Produto
from app.produtos.configs.models import MarcaProduto 

@produtos_bp.route("/api/buscar", methods=["GET"])
@login_required
def api_buscar_produtos():
    """
    Retorna lista de produtos do catálogo para Select2/Autocomplete.
    """
    termo = request.args.get("termo", "").strip()
    
    # Otimização: Carrega a marca junto
    query = Produto.query.options(joinedload(Produto.marca_rel))

    if termo:
        # Busca por Nome, Código ou Marca
        query = query.outerjoin(MarcaProduto).filter(
            or_(
                Produto.nome.ilike(f"%{termo}%"),
                Produto.codigo.ilike(f"%{termo}%"),
                MarcaProduto.nome.ilike(f"%{termo}%")
            )
        )
    
    # Limita resultados
    produtos = query.order_by(Produto.nome).limit(50).all()
    
    # Formato JSON para Select2
    resultado = [
        {
            "id": p.id,
            "text": f"{p.nome} ({p.codigo or 'S/C'})",
            "marca": p.marca_rel.nome if p.marca_rel else "",
            "codigo": p.codigo or ""
        }
        for p in produtos
    ]
    
    return jsonify(resultado)