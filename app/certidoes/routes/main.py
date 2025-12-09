# app/certidoes/routes/main.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.utils.datetime import now_local
from app.certidoes.models import Certidao, CertidaoStatus, CertidaoTipo
from app.clientes.models import Cliente
from app.utils.queue import fila_certidoes
from app.certidoes.tasks import emitir_certidao, tarefa_teste
from app.utils.storage import gerar_link_publico

certidoes_bp = Blueprint(
    "certidoes",
    __name__,
    template_folder="../templates",
)


# =========================================================
# LISTAGEM DE CERTIDÕES
# =========================================================
@certidoes_bp.route("/")
@login_required
def listar_certidoes():
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Filtros básicos (string na querystring)
    status_param = request.args.get("status") or None
    cliente_id = request.args.get("cliente_id", type=int)
    tipo_param = request.args.get("tipo") or None

    query = (
        Certidao.query.options(joinedload(Certidao.cliente))
        .order_by(Certidao.criado_em.desc())
    )

    # status_param -> Enum
    if status_param:
        status_enum = None
        try:
            status_enum = CertidaoStatus(status_param)  # pelo value (pendente, emitida...)
        except ValueError:
            try:
                status_enum = CertidaoStatus[status_param]  # pelo name (PENDENTE, EMITIDA...)
            except KeyError:
                status_enum = None

        if status_enum:
            query = query.filter(Certidao.status == status_enum)

    if cliente_id:
        query = query.filter(Certidao.cliente_id == cliente_id)

    # tipo_param -> Enum
    if tipo_param:
        tipo_enum = None
        try:
            tipo_enum = CertidaoTipo(tipo_param)
        except ValueError:
            try:
                tipo_enum = CertidaoTipo[tipo_param]
            except KeyError:
                tipo_enum = None

        if tipo_enum:
            query = query.filter(Certidao.tipo == tipo_enum)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    filtros = {
        "status": status_param,
        "cliente_id": cliente_id,
        "tipo": tipo_param,
    }

    return render_template(
        "certidoes/index.html",
        certidoes=pagination.items,
        pagination=pagination,
        filtros=filtros,
        CertidaoStatus=CertidaoStatus,
        CertidaoTipo=CertidaoTipo,
    )


# =========================================================
# CRIAR PACOTE DE CERTIDÕES PARA UM CLIENTE
# (TJPI, STM, TSE, TRF1)
# =========================================================
@certidoes_bp.route("/cliente/<int:cliente_id>/criar-pacote", methods=["POST"])
@login_required
def criar_pacote_certidoes(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    # Tipos padrão do pacote
    tipos_pacote = [
        CertidaoTipo.ESTADUAL_TJPI,
        CertidaoTipo.MILITAR_STM,
        CertidaoTipo.ELEITORAL_TSE,
        CertidaoTipo.FEDERAL_TRF1,
    ]

    # Quais tipos o cliente já tem
    tipos_existentes = {c.tipo for c in cliente.certidoes}

    criadas = 0
    for tipo in tipos_pacote:
        if tipo in tipos_existentes:
            continue

        cert = Certidao(
            cliente_id=cliente.id,
            tipo=tipo,
            status=CertidaoStatus.PENDENTE,
            data_solicitacao=now_local(),
            criado_em=now_local(),
            atualizado_em=now_local(),
            criado_por_id=current_user.id,
        )
        db.session.add(cert)
        criadas += 1

    if criadas > 0:
        db.session.commit()
        flash(f"{criadas} certidões foram criadas para {cliente.nome}.", "success")
    else:
        flash("Esse cliente já possui todas as certidões do pacote cadastradas.", "info")

    return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))


# =========================================================
# GERAR CERTIDÃO (usa emissão automática real)
# =========================================================
@certidoes_bp.route("/<int:certidao_id>/gerar", methods=["POST"])
@login_required
def gerar_certidao(certidao_id):
    cert = Certidao.query.get_or_404(certidao_id)

    # Atualiza para EM_PROCESSO antes de enviar para a fila
    cert.status = CertidaoStatus.EM_PROCESSO
    cert.atualizado_em = now_local()
    db.session.add(cert)
    db.session.commit()

    job = fila_certidoes.enqueue(emitir_certidao, certidao_id)
    current_app.logger.info(
        f"[CERTIDÕES] Certidão {certidao_id} enviada para fila (job_id={job.id})"
    )

    flash("Certidão enviada para processamento em segundo plano.", "info")
    return redirect(url_for("clientes.detalhe", cliente_id=cert.cliente_id))


# =========================================================
# DOWNLOAD / VISUALIZAÇÃO DO ARQUIVO (R2)
# =========================================================
@certidoes_bp.route("/<int:certidao_id>/download")
@login_required
def baixar_certidao(certidao_id):
    cert = Certidao.query.get_or_404(certidao_id)

    if not cert.arquivo_storage_key:
        flash("Esta certidão ainda não possui arquivo anexado.", "warning")
        return redirect(url_for("certidoes.listar_certidoes"))

    try:
        url = gerar_link_publico(cert.arquivo_storage_key, expira_segundos=3600)
        return redirect(url)
    except Exception as e:
        current_app.logger.exception(
            f"[CERTIDÕES] Erro ao gerar link público da certidão {cert.id}: {e}"
        )
        flash("Não foi possível abrir o arquivo desta certidão.", "danger")
        return redirect(url_for("certidoes.listar_certidoes"))


# =========================================================
# ENDPOINTS DE COMPATIBILIDADE COM TEMPLATES ANTIGOS
# =========================================================

@certidoes_bp.route("/<int:certidao_id>/atualizar", methods=["POST"])
@login_required
def atualizar_certidao(certidao_id):
    """
    Compatibilidade com forms/links antigos que postam para
    certidoes.atualizar_certidao.
    Se vier 'status' no form, tenta atualizar o status.
    """
    cert = Certidao.query.get_or_404(certidao_id)
    novo_status = request.form.get("status")

    if novo_status:
        try:
            # tenta tratar como value (pendente, emitida, ...)
            status_enum = CertidaoStatus(novo_status)
        except ValueError:
            try:
                # ou como name (PENDENTE, EMITIDA, ...)
                status_enum = CertidaoStatus[novo_status]
            except KeyError:
                status_enum = None

        if status_enum:
            cert.status = status_enum
            cert.atualizado_em = now_local()
            db.session.add(cert)
            db.session.commit()
            flash("Status da certidão atualizado com sucesso.", "success")
        else:
            flash("Status informado inválido.", "danger")

    return redirect(url_for("clientes.detalhe", cliente_id=cert.cliente_id))


@certidoes_bp.route("/<int:certidao_id>/arquivo")
@login_required
def baixar_arquivo(certidao_id):
    """
    Compatibilidade com templates que ainda usam
    url_for('certidoes.baixar_arquivo', certidao_id=...).
    Apenas delega para baixar_certidao.
    """
    return baixar_certidao(certidao_id)


# =========================================================
# ROTA DE TESTE SIMPLES PARA A FILA (DEBUG)
# =========================================================
@certidoes_bp.route("/teste/<int:certidao_id>")
@login_required
def teste_fila(certidao_id):
    job = fila_certidoes.enqueue(tarefa_teste, certidao_id)
    current_app.logger.info(
        f"[CERTIDÕES] Job de teste enfileirado para certidão={certidao_id} job_id={job.id}"
    )
    return f"Job enviado para certidão {certidao_id}: {job.id}", 200
