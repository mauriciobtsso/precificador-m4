# ======================
# PRODUTOS CONFIGS - ROUTES (CRUD AJAX)
# ======================

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from datetime import datetime
from app import db
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto

configs_bp = Blueprint(
    "produtos_configs",
    __name__,
    url_prefix="/produtos/configs",
    template_folder="templates"
)

# ======================
# INDEX - LISTAR TUDO
# ======================

@configs_bp.route("/")
@login_required
def index():
    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome).all()
    tipos = TipoProduto.query.order_by(TipoProduto.nome).all()
    funcionamentos = FuncionamentoProduto.query.order_by(FuncionamentoProduto.nome).all()

    return render_template(
        "produtos_configs/index.html",
        categorias=categorias,
        marcas=marcas,
        calibres=calibres,
        tipos=tipos,
        funcionamentos=funcionamentos
    )


# ======================
# ADICIONAR ITEM (com verificação de duplicado)
# ======================

@configs_bp.route("/adicionar/<tabela>", methods=["POST"])
@login_required
def adicionar_item(tabela):
    data = request.get_json()
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()

    if not nome:
        return jsonify({"error": "Nome é obrigatório."}), 400

    modelos = {
        "categoria": CategoriaProduto,
        "marca": MarcaProduto,
        "calibre": CalibreProduto,
        "tipo": TipoProduto,
        "funcionamento": FuncionamentoProduto,
    }

    modelo = modelos.get(tabela)
    if not modelo:
        return jsonify({"error": "Tabela inválida."}), 400

    # 🔎 Verificar duplicado
    existente = modelo.query.filter(
        db.func.lower(modelo.nome) == nome.lower()
    ).first()
    if existente:
        return jsonify({"error": f"Já existe um(a) {tabela} com esse nome."}), 409

    item = modelo(nome=nome, descricao=descricao, criado_em=datetime.now())
    db.session.add(item)
    db.session.commit()
    return jsonify({"success": True, "id": item.id})


# ======================
# EDITAR ITEM (com verificação de duplicado)
# ======================

@configs_bp.route("/editar/<tabela>/<int:item_id>", methods=["PUT"])
@login_required
def editar_item(tabela, item_id):
    data = request.get_json()
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()

    modelos = {
        "categoria": CategoriaProduto,
        "marca": MarcaProduto,
        "calibre": CalibreProduto,
        "tipo": TipoProduto,
        "funcionamento": FuncionamentoProduto,
    }

    modelo = modelos.get(tabela)
    if not modelo:
        return jsonify({"error": "Tabela inválida."}), 400

    # 🔎 Verificar duplicado (excluindo o próprio item)
    duplicado = modelo.query.filter(
        db.func.lower(modelo.nome) == nome.lower(),
        modelo.id != item_id
    ).first()
    if duplicado:
        return jsonify({"error": f"Já existe um(a) {tabela} com esse nome."}), 409

    item = modelo.query.get_or_404(item_id)
    item.nome = nome
    item.descricao = descricao
    item.atualizado_em = datetime.now()
    db.session.commit()
    return jsonify({"success": True})


# ======================
# EXCLUIR ITEM
# ======================

@configs_bp.route("/excluir/<tabela>/<int:item_id>", methods=["DELETE"])
@login_required
def excluir_item(tabela, item_id):
    modelos = {
        "categoria": CategoriaProduto,
        "marca": MarcaProduto,
        "calibre": CalibreProduto,
        "tipo": TipoProduto,
        "funcionamento": FuncionamentoProduto,
    }

    modelo = modelos.get(tabela)
    if not modelo:
        return jsonify({"error": "Tabela inválida."}), 400

    item = modelo.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True})
