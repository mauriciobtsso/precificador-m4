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
from redis.exceptions import ConnectionError as RedisConnectionError

from app.extensions import db
from app.utils.datetime import now_local
from app.certidoes.models import Certidao, CertidaoStatus, CertidaoTipo
from app.clientes.models import Cliente
from app.utils.storage import gerar_link_publico

# IMPORTS DA FILA E TAREFAS
from app.utils.queue import fila_certidoes
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
# GERAR CERTIDÃO (HÍBRIDO: Fila ou Síncrono)
# =========================================================
@certidoes_bp.route("/<int:certidao_id>/gerar", methods=["POST"])
@login_required
def gerar_certidao(certidao_id):
    cert = Certidao.query.get_or_404(certidao_id)

    # Atualiza status inicial
    cert.status = CertidaoStatus.EM_PROCESSO
    db.session.commit()

    # VERIFICAÇÃO INTELIGENTE DA FILA
    if fila_certidoes:
        # --- MODO ASSÍNCRONO (Produção / Redis Online) ---
        try:
            job = fila_certidoes.enqueue(emitir_certidao, certidao_id)
            current_app.logger.info(
                f"[CERTIDOES] Job enviado para fila Redis. Job ID: {job.id}"
            )
            flash("Certidão enviada para processamento em segundo plano.", "info")
        
        except Exception as e:
            current_app.logger.error(f"[CERTIDOES] Erro ao enfileirar job: {e}")
            # Se falhar ao colocar na fila, tenta síncrono ou avisa erro
            cert.status = CertidaoStatus.ERRO
            cert.observacoes = "Falha de conexão com a fila de processamento."
            db.session.commit()
            flash("Erro ao conectar ao serviço de filas. Tente novamente mais tarde.", "danger")

    else:
        # --- MODO SÍNCRONO (Local / Fallback) ---
        current_app.logger.warning(
            f"[CERTIDOES] Redis não disponível. Executando certidão {certidao_id} Sincronamente."
        )
        try:
            # Chama a função diretamente (vai travar o navegador por 1-3 segundos, normal)
            emitir_certidao(certidao_id)
            flash("Certidão processada e emitida com sucesso (Modo Local).", "success")
        except Exception as e:
            current_app.logger.exception(f"[CERTIDOES] Erro na execução síncrona: {e}")
            # A função emitir_certidao já trata o status ERRO no banco, 
            # aqui só garantimos o feedback visual.
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


# =========================================================
# ROTA DE TESTE (Mantida para Debug)
# =========================================================
@certidoes_bp.route("/teste/<int:certidao_id>")
@login_required
def teste_fila(certidao_id):
    if fila_certidoes:
        job = fila_certidoes.enqueue(emitir_certidao, certidao_id)
        return f"Job enviado: {job.id}", 200
    else:
        return "Redis desconectado. Teste não realizado via fila.", 500