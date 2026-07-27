# app/clientes/routes/documentos.py

from flask import (
    render_template, request, redirect, url_for,
    flash, current_app
)

from werkzeug.utils import secure_filename

from app import db
from app.clientes import clientes_bp
from app.clientes.models import Cliente, Documento
from app.clientes.constants import CATEGORIAS_DOCUMENTO, EMISSORES_DOCUMENTO

# Importações Táticas M4 (Helpers e Storage)
from app.utils.r2_helpers import gerar_link_r2, upload_file_to_r2
from app.utils.storage import deletar_arquivo
from app.utils.datetime import now_local
from app.clientes.routes.helpers import parse_date


# =================================================
# REDIRECIONA PARA A ABA DOCUMENTOS NO DETALHE
# =================================================
@clientes_bp.route("/<int:cliente_id>/documentos")
def documentos(cliente_id):
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# =================================================
# NOVO DOCUMENTO (manual + OCR)
# =================================================
@clientes_bp.route("/<int:cliente_id>/documentos/novo", methods=["POST"])
def novo_documento(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    categoria = request.form.get("categoria")
    tipo = categoria or request.form.get("tipo")
    emissor = request.form.get("emissor")
    numero = request.form.get("numero_documento")
    validade_indeterminada = bool(request.form.get("validade_indeterminada"))
    observacoes = request.form.get("observacoes")
    
    # Recebe caminho se já processado via OCR no JS, senão None
    caminho_arquivo = request.form.get("caminho_arquivo") or None
    nome_original = request.form.get("arquivo") or None

    # Upload manual usando o R2 Helper
    if not caminho_arquivo and "arquivo" in request.files and request.files["arquivo"].filename:
        file = request.files["arquivo"]
        nome_seguro = secure_filename(file.filename)
        timestamp = now_local().strftime("%Y%m%d_%H%M%S")
        
        # Alteramos o nome do arquivo em memória para garantir a unicidade no R2
        file.filename = f"{timestamp}_{nome_seguro}"
        
        pasta_destino = f"clientes/{cliente_id}/documentos"
        caminho_arquivo = upload_file_to_r2(file, folder=pasta_destino)
        
        # Guardamos o nome seguro original para exibição limpa no front-end
        nome_original = nome_seguro

    documento = Documento(
        cliente_id=cliente.id,
        tipo=tipo,
        categoria=categoria,
        emissor=emissor,
        numero_documento=numero,
        data_emissao=parse_date(request.form.get("data_emissao")),
        data_validade=parse_date(request.form.get("data_validade")),
        validade_indeterminada=validade_indeterminada,
        observacoes=observacoes,
        caminho_arquivo=caminho_arquivo,
        nome_original=nome_original,
        data_upload=now_local(),
    )

    db.session.add(documento)
    db.session.commit()
    flash("Documento cadastrado com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id, _anchor="documentos"))


# =================================================
# FORMULÁRIO DINÂMICO (GET) + EDIÇÃO DE DOCUMENTO
# =================================================
@clientes_bp.route("/<int:cliente_id>/documentos/<int:doc_id>/editar", methods=["GET", "POST"])
def editar_documento(cliente_id, doc_id):
    documento = Documento.query.get_or_404(doc_id)
    cliente = Cliente.query.get_or_404(cliente_id)

    # GET — Renderiza modal parcial
    if request.method == "GET":
        return render_template(
            "clientes/abas/documentos_editar.html",
            cliente=cliente,
            doc=documento,
            CATEGORIAS_DOCUMENTO=CATEGORIAS_DOCUMENTO,
            EMISSORES_DOCUMENTO=EMISSORES_DOCUMENTO,
        )

    # POST — Salva alterações
    documento.categoria = request.form.get("categoria")
    documento.tipo = documento.categoria or request.form.get("tipo")
    documento.emissor = request.form.get("emissor")
    documento.numero_documento = request.form.get("numero_documento")
    documento.observacoes = request.form.get("observacoes")
    documento.validade_indeterminada = bool(request.form.get("validade_indeterminada"))

    # Conversão de datas centralizada via helper
    documento.data_emissao = parse_date(request.form.get("data_emissao"))
    documento.data_validade = parse_date(request.form.get("data_validade"))

    # Substituição de arquivo (manual ou OCR)
    novo_caminho = request.form.get("caminho_arquivo")
    field_name = f"arquivoEditar{doc_id}"

    if field_name in request.files and request.files[field_name].filename:
        file = request.files[field_name]
        nome_seguro = secure_filename(file.filename)
        timestamp = now_local().strftime("%Y%m%d_%H%M%S")
        
        # Unicidade do arquivo
        file.filename = f"{timestamp}_{nome_seguro}"
        
        pasta_destino = f"clientes/{cliente_id}/documentos"
        caminho_upload = upload_file_to_r2(file, folder=pasta_destino)
        
        if caminho_upload:
            novo_caminho = caminho_upload
            documento.nome_original = nome_seguro

    if novo_caminho:
        documento.caminho_arquivo = novo_caminho
        documento.data_upload = now_local()

    db.session.commit()
    flash("Documento atualizado com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# =================================================
# DELETAR DOCUMENTO
# =================================================
@clientes_bp.route("/<int:cliente_id>/documentos/<int:doc_id>/deletar", methods=["POST"])
def deletar_documento(cliente_id, doc_id):
    documento = Documento.query.get_or_404(doc_id)
    caminho_arquivo_para_deletar = documento.caminho_arquivo

    try:
        db.session.delete(documento)
        db.session.commit()

        # O helper deletar_arquivo processa de forma segura a exclusão no R2
        if caminho_arquivo_para_deletar:
            deletar_arquivo(caminho_arquivo_para_deletar)

        flash("Documento removido com sucesso!", "info")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao deletar documento {doc_id}: {e}")
        flash("Erro ao remover o documento.", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="documentos"))


# =================================================
# ABRIR DOCUMENTO (R2)
# =================================================
@clientes_bp.route("/documentos/<int:doc_id>/abrir")
def abrir_documento(doc_id):
    documento = Documento.query.get_or_404(doc_id)

    if not documento.caminho_arquivo:
        flash("Nenhum arquivo enviado para este documento.", "warning")
        return redirect(request.referrer or url_for("clientes.index"))

    try:
        link = gerar_link_r2(documento.caminho_arquivo)
        return redirect(link)
    except Exception as e:
        flash(f"Erro ao gerar link do arquivo: {e}", "danger")
        return redirect(request.referrer or url_for("clientes.index"))