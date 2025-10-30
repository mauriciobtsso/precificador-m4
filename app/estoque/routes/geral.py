from flask import jsonify
from flask_login import login_required
from app.estoque import estoque_bp
from app.produtos.models import Produto, TipoProduto


@estoque_bp.route("/api/status")
@login_required
def estoque_status():
    """Endpoint simples de verificação"""
    return jsonify({"ok": True, "mensagem": "Módulo Estoque ativo"})


@estoque_bp.route("/api/produtos/<string:tipo_nome>")
@login_required
def produtos_por_tipo(tipo_nome):
    """
    Retorna produtos filtrados pelo tipo (arma, municao, pce, etc.)
    Exemplo: /estoque/api/produtos/municao
    """
    tipo_nome = tipo_nome.lower()

    # Mapeamento de URL → nome real no banco
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
            "marca": p.marca.nome if getattr(p, "marca", None) else ""
        }
        for p in produtos
    ]
    return jsonify(resultado)
