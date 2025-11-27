from flask import jsonify, request
from flask_login import login_required
from sqlalchemy.orm import joinedload
from app.estoque import estoque_bp
from app.produtos.models import Produto, TipoProduto, MarcaProduto
from sqlalchemy import or_

@estoque_bp.route("/api/status")
@login_required
def estoque_status():
    return jsonify({"ok": True, "mensagem": "Módulo Estoque ativo"})

# === ROTA OTIMIZADA PARA O SELECT2 ===
@estoque_bp.route("/api/produtos/todos")
@login_required
def produtos_todos():
    termo = request.args.get('termo', '').strip()
    
    # Otimização: Carrega a Marca junto para não fazer query extra no loop
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
    
    # Retorna os 30 primeiros para ser rápido
    produtos = query.order_by(Produto.nome).limit(30).all()

    resultado = [
        {
            "id": p.id,
            "nome": p.nome,
            "codigo": p.codigo or "",
            # Garante que não quebra se marca for None
            "marca": p.marca_rel.nome if getattr(p, 'marca_rel', None) else ""
        }
        for p in produtos
    ]
    return jsonify(resultado)


# Rota Legada (Mantida para compatibilidade)
@estoque_bp.route("/api/produtos/<string:tipo_nome>")
@login_required
def produtos_por_tipo(tipo_nome):
    tipo_nome = tipo_nome.lower()
    map_tipos = {
        "arma": "Arma de Fogo",
        "municao": "Munição",
        "pce": "PCE",
        "nao_controlado": "Não Controlado",
    }
    nome_real = map_tipos.get(tipo_nome, tipo_nome)

    produtos = (
        Produto.query
        .join(TipoProduto)
        .filter(TipoProduto.nome.ilike(f"%{nome_real}%"))
        .order_by(Produto.nome)
        .all()
    )

    resultado = [
        {
            "id": p.id,
            "nome": p.nome,
            "codigo": p.codigo or "",
            "marca": p.marca_rel.nome if getattr(p, 'marca_rel', None) else ""
        }
        for p in produtos
    ]
    return jsonify(resultado)