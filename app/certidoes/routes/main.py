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
from app.utils.storage import gerar_link_publico

from app.certidoes.tasks import emitir_certidao

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

    status_value = request.args.get("status") or None
    cliente_id = request.args.get("cliente_id", type=int)
    tipo_value = request.args.get("tipo") or None

    query = (
        Certidao.query.options(joinedload(Certidao.cliente))
        .order_by(Certidao.criado_em.desc())
    )

    if status_value:
        try:
            status_enum = CertidaoStatus(status_value)
            query = query.filter(Certidao.status == status_enum)
        except ValueError:
            pass

    if cliente_id:
        query = query.filter(Certidao.cliente_id == cliente_id)

    if tipo_value:
        try:
            tipo_enum = CertidaoTipo(tipo_value)
            query = query.filter(Certidao.tipo == tipo_enum)
        except ValueError:
            pass

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    filtros = {
        "status": status_value,
        "cliente_id": cliente_id,
        "tipo": tipo_value,
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
# =========================================================
@certidoes_bp.route("/cliente/<int:cliente_id>/criar-pacote", methods=["POST"])
@login_required
def criar_pacote_certidoes(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    tipos_pacote = [
        CertidaoTipo.ESTADUAL_TJPI,
        CertidaoTipo.MILITAR_STM,
        CertidaoTipo.ELEITORAL_TSE,
        CertidaoTipo.FEDERAL_TRF1,
    ]

    tipos_existentes = {c.tipo for c in cliente.certidoes}

    criadas = 0
    for tipo in tipos_pacote:
        if tipo in tipos_existentes:
            continue

        cert = Certidao(
            cliente_id=cliente.id,
            tipo=tipo,
            status=CertidaoStatus.PENDENTE,
            criado_em=now_local(),
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
# GERAR CERTIDÃO (100% SÍNCRONO, SEM FILA)
# =========================================================
@certidoes_bp.route("/<int:certidao_id>/gerar", methods=["POST"])
@login_required
def gerar_certidao(certidao_id):
    cert = Certidao.query.get_or_404(certidao_id)

    try:
        current_app.logger.info(
            f"[CERTIDOES] Iniciando emissão síncrona da certidão #{cert.id}"
        )
        emitir_certidao(certidao_id)
        flash("Certidão emitida com sucesso.", "success")
    except Exception as e:
        current_app.logger.exception(
            f"[CERTIDOES] Erro na emissão síncrona da certidão #{cert.id}: {e}"
        )
        flash("Ocorreu um erro ao gerar a certidão.", "danger")

    return redirect(url_for("certidoes.listar_certidoes"))


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
