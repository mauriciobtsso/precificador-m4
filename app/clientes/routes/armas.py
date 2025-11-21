from flask import (
    render_template, request, redirect, url_for,
    flash, current_app
)
from datetime import datetime
from werkzeug.utils import secure_filename

from app import db
from app.clientes import clientes_bp
from app.clientes.models import Cliente, Arma
from app.clientes.constants import (
    TIPOS_ARMA, FUNCIONAMENTO_ARMA, EMISSORES_CRAF,
    CATEGORIAS_ADQUIRENTE
)
from app.utils.storage import get_s3, get_bucket, deletar_arquivo
from app.utils.r2_helpers import gerar_link_r2
from app.utils.datetime import now_local


@clientes_bp.route("/<int:cliente_id>/armas", methods=["GET"])
def cliente_armas(cliente_id):
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


@clientes_bp.route("/<int:cliente_id>/armas/nova", methods=["GET"])
def form_nova_arma(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template(
        "clientes/abas/armas_nova.html",
        cliente=cliente,
        TIPOS_ARMA=TIPOS_ARMA,
        FUNCIONAMENTO_ARMA=FUNCIONAMENTO_ARMA,
        EMISSORES_CRAF=EMISSORES_CRAF,
        CATEGORIAS_ADQUIRENTE=CATEGORIAS_ADQUIRENTE,
    )


@clientes_bp.route("/<int:cliente_id>/armas/nova", methods=["POST"])
def nova_arma(cliente_id):
    num_serie = request.form.get("numero_serie")
    if num_serie and Arma.query.filter_by(numero_serie=num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    tipo = request.form.get("tipo") or None
    funcionamento = request.form.get("funcionamento") or None
    marca = request.form.get("marca") or None
    modelo = request.form.get("modelo") or None
    calibre = request.form.get("calibre") or None
    emissor_craf = request.form.get("emissor_craf") or None
    numero_sigma = request.form.get("numero_sigma") or None
    categoria_adquirente = request.form.get("categoria_adquirente") or None
    validade_indeterminada = bool(request.form.get("validade_indeterminada"))
    data_validade = request.form.get("data_validade_craf") or None

    data_validade_parsed = None
    if data_validade:
        try:
            data_validade_parsed = datetime.strptime(data_validade, "%Y-%m-%d").date()
        except ValueError:
            data_validade_parsed = None

    caminho = request.form.get("caminho_craf") or None

    if not caminho and "arquivo" in request.files and request.files["arquivo"].filename:
        file = request.files["arquivo"]
        nome_seguro = secure_filename(file.filename)
        timestamp = now_local().strftime("%Y%m%d_%H%M%S")
        caminho = f"clientes/{cliente_id}/armas/{timestamp}_{nome_seguro}"
        s3 = get_s3()
        bucket = get_bucket()
        file.seek(0)
        s3.upload_fileobj(file, bucket, caminho)

    arma = Arma(
        cliente_id=cliente_id,
        tipo=tipo,
        funcionamento=funcionamento,
        marca=marca,
        modelo=modelo,
        calibre=calibre,
        numero_serie=num_serie,
        emissor_craf=emissor_craf,
        numero_sigma=numero_sigma,
        categoria_adquirente=categoria_adquirente,
        validade_indeterminada=validade_indeterminada,
        data_validade_craf=data_validade_parsed,
        caminho_craf=caminho,
    )

    db.session.add(arma)
    db.session.commit()

    flash("Arma cadastrada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/editar", methods=["GET"])
def form_editar_arma(cliente_id, arma_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    arma = Arma.query.get_or_404(arma_id)
    return render_template(
        "clientes/abas/armas_editar.html",
        cliente=cliente,
        arma=arma,
        TIPOS_ARMA=TIPOS_ARMA,
        FUNCIONAMENTO_ARMA=FUNCIONAMENTO_ARMA,
        EMISSORES_CRAF=EMISSORES_CRAF,
        CATEGORIAS_ADQUIRENTE=CATEGORIAS_ADQUIRENTE,
    )


@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/editar", methods=["POST"])
def editar_arma(cliente_id, arma_id):
    arma = Arma.query.get_or_404(arma_id)

    num_serie = request.form.get("numero_serie")
    if num_serie and Arma.query.filter(Arma.id != arma.id, Arma.numero_serie == num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    arma.tipo = request.form.get("tipo") or None
    arma.funcionamento = request.form.get("funcionamento") or None
    arma.marca = request.form.get("marca") or None
    arma.modelo = request.form.get("modelo") or None
    arma.calibre = request.form.get("calibre") or None
    arma.numero_serie = num_serie or None
    arma.emissor_craf = request.form.get("emissor_craf") or None
    arma.numero_sigma = request.form.get("numero_sigma") or None
    arma.categoria_adquirente = request.form.get("categoria_adquirente") or None
    arma.validade_indeterminada = bool(request.form.get("validade_indeterminada"))

    data_validade = request.form.get("data_validade_craf") or None
    if data_validade:
        try:
            arma.data_validade_craf = datetime.strptime(data_validade, "%Y-%m-%d").date()
        except ValueError:
            arma.data_validade_craf = None
    else:
        arma.data_validade_craf = None

    novo_caminho = request.form.get("caminho_craf") or None

    if not novo_caminho and "arquivo" in request.files and request.files["arquivo"].filename:
        file = request.files["arquivo"]
        nome_seguro = secure_filename(file.filename)
        timestamp = now_local().strftime("%Y%m%d_%H%M%S")
        novo_caminho = f"clientes/{cliente_id}/armas/{timestamp}_{nome_seguro}"

        if arma.caminho_craf:
            deletar_arquivo(arma.caminho_craf)

        s3 = get_s3()
        bucket = get_bucket()
        file.seek(0)
        s3.upload_fileobj(file, bucket, novo_caminho)

    if novo_caminho:
        arma.caminho_craf = novo_caminho

    db.session.commit()
    flash("Arma atualizada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


@clientes_bp.route("/<int:cliente_id>/armas/salvar", methods=["POST"])
def salvar_craf(cliente_id):
    num_serie = request.form.get("numero_serie")
    if num_serie and Arma.query.filter_by(numero_serie=num_serie).first():
        flash(f"Já existe arma com número de série {num_serie}", "warning")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))

    tipo = request.form.get("tipo") or None
    funcionamento = request.form.get("funcionamento") or None
    marca = request.form.get("marca") or None
    modelo = request.form.get("modelo") or None
    calibre = request.form.get("calibre") or None
    emissor_craf = request.form.get("emissor_craf") or None
    numero_sigma = request.form.get("numero_sigma") or None
    categoria_adquirente = request.form.get("categoria_adquirente") or None
    validade_indeterminada = bool(request.form.get("validade_indeterminada"))
    data_validade = request.form.get("data_validade_craf") or None
    caminho = request.form.get("caminho_craf") or None

    data_validade_parsed = None
    if data_validade:
        try:
            data_validade_parsed = datetime.strptime(data_validade, "%Y-%m-%d").date()
        except ValueError:
            data_validade_parsed = None

    arma = Arma(
        cliente_id=cliente_id,
        tipo=tipo,
        funcionamento=funcionamento,
        marca=marca,
        modelo=modelo,
        calibre=calibre,
        numero_serie=num_serie,
        emissor_craf=emissor_craf,
        numero_sigma=numero_sigma,
        categoria_adquirente=categoria_adquirente,
        validade_indeterminada=validade_indeterminada,
        data_validade_craf=data_validade_parsed,
        caminho_craf=caminho,
    )

    db.session.add(arma)
    db.session.commit()

    flash("Arma cadastrada com sucesso!", "success")
    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


@clientes_bp.route("/<int:cliente_id>/armas/<int:arma_id>/deletar", methods=["POST"])
def deletar_arma(cliente_id, arma_id):
    arma = Arma.query.get_or_404(arma_id)
    caminho_arquivo = arma.caminho_craf

    try:
        db.session.delete(arma)
        db.session.commit()

        if caminho_arquivo:
            deletar_arquivo(caminho_arquivo)

        flash("Arma excluída com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir arma {arma_id}: {e}")
        flash("Erro ao excluir arma.", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente_id, _anchor="armas"))


@clientes_bp.route("/armas/<int:arma_id>/abrir")
def abrir_craf(arma_id):
    arma = Arma.query.get_or_404(arma_id)

    if not arma.caminho_craf:
        flash("Arquivo não encontrado", "danger")
        return redirect(url_for("clientes.detalhe", cliente_id=arma.cliente_id, _anchor="armas"))

    url = gerar_link_r2(arma.caminho_craf)
    return redirect(url)
