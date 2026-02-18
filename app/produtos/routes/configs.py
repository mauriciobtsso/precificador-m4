import uuid
from flask import request, jsonify, current_app
from flask_login import login_required
from app import db
from app.produtos import produtos_bp
from app.produtos.configs.models import MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto
from app.produtos.categorias.models import CategoriaProduto
from .utils import _r2_bucket, _r2_client, _r2_public_base, _guess_ext

# Helper para mapear tabelas
def get_model(tabela):
    mapa = {
        'categoria': CategoriaProduto,
        'marca': MarcaProduto,
        'calibre': CalibreProduto,
        'tipo': TipoProduto,
        'funcionamento': FuncionamentoProduto
    }
    return mapa.get(tabela)

@produtos_bp.route("/configs/adicionar/<string:tabela>", methods=["POST"])
@login_required
def adicionar_config_geral(tabela):
    Model = get_model(tabela)
    if not Model:
        return jsonify(success=False, error="Tabela inválida"), 400

    # Captura dados (FormData para marcas, JSON para o resto)
    nome = request.form.get("nome") or (request.json.get("nome") if request.is_json else None)
    descricao = request.form.get("descricao") or (request.json.get("descricao") if request.is_json else None)
    
    if not nome:
        return jsonify(success=False, error="Nome é obrigatório"), 400

    try:
        novo_item = Model(nome=nome, descricao=descricao)

        # Lógica de Logo exclusiva para Marcas
        if tabela == "marca":
            arquivo = request.files.get("logo")
            if arquivo:
                content_type = arquivo.mimetype or "image/png"
                ext = _guess_ext(content_type)
                # Definimos a KEY (o caminho dentro do balde R2)
                key = f"produtos/marcas/logos/{uuid.uuid4().hex}{ext}"
                
                bucket = _r2_bucket()
                client = _r2_client()
                arquivo.seek(0)
                client.upload_fileobj(
                    Fileobj=arquivo, 
                    Bucket=bucket, 
                    Key=key, 
                    ExtraArgs={"ContentType": content_type}
                )
                
                # CORREÇÃO AQUI: Salvamos apenas a key. 
                # Não colocamos o base_public aqui para evitar URLs duplicadas.
                item.logo_url = key

        db.session.add(novo_item)
        db.session.commit()
        return jsonify(success=True, id=novo_item.id, nome=novo_item.nome), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500

@produtos_bp.route("/configs/editar/<string:tabela>/<int:id>", methods=["POST", "PUT"])
@login_required
def editar_config_geral(tabela, id):
    Model = get_model(tabela)
    item = Model.query.get_or_404(id)

    # Captura dados
    nome = request.form.get("nome") or (request.json.get("nome") if request.is_json else None)
    descricao = request.form.get("descricao") or (request.json.get("descricao") if request.is_json else None)

    if not nome:
        return jsonify(success=False, error="Nome é obrigatório"), 400

    try:
        item.nome = nome
        item.descricao = descricao

        # Atualização de Logo para Marcas
        if tabela == "marca":
            arquivo = request.files.get("logo")
            if arquivo:
                content_type = arquivo.mimetype or "image/png"
                ext = _guess_ext(content_type)
                key = f"produtos/marcas/logos/{uuid.uuid4().hex}{ext}"
                
                bucket = _r2_bucket()
                client = _r2_client()
                arquivo.seek(0)
                client.upload_fileobj(Fileobj=arquivo, Bucket=bucket, Key=key, ExtraArgs={"ContentType": content_type})
                
                base_public = _r2_public_base()
                item.logo_url = f"{base_public.rstrip('/')}/{key}"

        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500

@produtos_bp.route("/configs/excluir/<string:tabela>/<int:id>", methods=["DELETE"])
@login_required
def excluir_config_geral(tabela, id):
    Model = get_model(tabela)
    item = Model.query.get_or_404(id)
    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error="Não é possível excluir: este item está em uso por produtos."), 500