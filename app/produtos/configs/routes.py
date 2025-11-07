# ======================================================
# PRODUTOS CONFIGS - ROUTES (CRUD AJAX) — Versão Estável
# ======================================================

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app import db
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto,
    CalibreProduto,
    TipoProduto,
    FuncionamentoProduto,
)

configs_bp = Blueprint(
    "produtos_configs",
    __name__,
    url_prefix="/produtos/configs",
    template_folder="templates",
)

# ======================================================
# MODELOS DISPONÍVEIS
# ======================================================
MODELOS = {
    "categoria": CategoriaProduto,
    "marca": MarcaProduto,
    "calibre": CalibreProduto,
    "tipo": TipoProduto,
    "funcionamento": FuncionamentoProduto,
}


# ======================================================
# INDEX — LISTAR TUDO
# ======================================================
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
        funcionamentos=funcionamentos,
    )


# ======================================================
# FUNÇÃO AUXILIAR — Corrigir sequência defasada
# ======================================================
def _corrigir_sequence(nome_tabela: str):
    """Corrige automaticamente a sequência defasada no PostgreSQL."""
    try:
        sql = text(f"""
            SELECT setval(
                pg_get_serial_sequence('{nome_tabela}', 'id'),
                COALESCE((SELECT MAX(id) FROM {nome_tabela}), 1),
                TRUE
            );
        """)
        db.session.execute(sql)
        db.session.commit()
        current_app.logger.info(f"[M4 Configs] Sequência corrigida para {nome_tabela}")
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[M4 Configs] Falha ao corrigir sequência de {nome_tabela}: {e}")
        return False

# ======================================================
# ADICIONAR ITEM — Com validação e autocorreção de sequência
# ======================================================
@configs_bp.route("/adicionar/<tabela>", methods=["POST"])
@login_required
def adicionar_item(tabela):
    data = request.get_json() or {}
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()

    if not nome:
        return jsonify({"error": "Nome é obrigatório."}), 400

    modelo = MODELOS.get(tabela)
    if not modelo:
        return jsonify({"error": "Tabela inválida."}), 400

    # 🔍 Verifica duplicidade de nome
    existente = modelo.query.filter(
        db.func.lower(modelo.nome) == nome.lower()
    ).first()
    if existente:
        return jsonify({"error": f"Já existe um(a) {tabela} com esse nome."}), 409

    try:
        item = modelo(nome=nome, descricao=descricao, criado_em=datetime.now())
        db.session.add(item)
        db.session.commit()
        return jsonify({"success": True, "id": item.id})

    except IntegrityError as e:
        db.session.rollback()
        if "duplicate key value violates unique constraint" in str(e):
            _corrigir_sequence(modelo.__tablename__)
            return jsonify({
                "error": f"Erro de sequência detectado em {tabela}. A sequência foi corrigida, tente novamente."
            }), 500
        return jsonify({"error": f"Erro de integridade: {e}"}), 500

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[M4 Configs] Erro ao adicionar {tabela}: {e}")
        return jsonify({"error": f"Erro inesperado: {e}"}), 500


# ======================================================
# EDITAR ITEM — Com verificação de duplicidade
# ======================================================
@configs_bp.route("/editar/<tabela>/<int:item_id>", methods=["PUT"])
@login_required
def editar_item(tabela, item_id):
    data = request.get_json() or {}
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()

    modelo = MODELOS.get(tabela)
    if not modelo:
        return jsonify({"error": "Tabela inválida."}), 400

    # 🔎 Verifica duplicidade (excluindo o próprio item)
    duplicado = modelo.query.filter(
        db.func.lower(modelo.nome) == nome.lower(),
        modelo.id != item_id,
    ).first()
    if duplicado:
        return jsonify({"error": f"Já existe um(a) {tabela} com esse nome."}), 409

    item = modelo.query.get_or_404(item_id)
    item.nome = nome
    item.descricao = descricao
    item.atualizado_em = datetime.now()

    try:
        db.session.commit()
        return jsonify({"success": True})
    except IntegrityError as e:
        db.session.rollback()
        if "duplicate key value violates unique constraint" in str(e):
            _corrigir_sequence(modelo.__tablename__)
            return jsonify({
                "error": f"Erro de sequência detectado em {tabela}. A sequência foi corrigida, tente novamente."
            }), 500
        return jsonify({"error": f"Erro de integridade: {e}"}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[M4 Configs] Erro ao editar {tabela}: {e}")
        return jsonify({"error": f"Erro inesperado: {e}"}), 500


# ======================================================
# EXCLUIR ITEM — Com rollback seguro
# ======================================================
@configs_bp.route("/excluir/<tabela>/<int:item_id>", methods=["DELETE"])
@login_required
def excluir_item(tabela, item_id):
    modelo = MODELOS.get(tabela)
    if not modelo:
        return jsonify({"error": "Tabela inválida."}), 400

    item = modelo.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"success": True})
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"[M4 Configs] Violação de integridade ao excluir {tabela}: {e}")
        return jsonify({"error": f"Erro de integridade ao excluir {tabela}: {e}"}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[M4 Configs] Erro ao excluir {tabela}: {e}")
        return jsonify({"error": f"Erro inesperado: {e}"}), 500
