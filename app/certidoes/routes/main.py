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
from app.clientes.models import Cliente, DadosDeclaracaoResidencia
from app.utils.storage import gerar_link_publico

from app.certidoes.tasks import emitir_certidao
from app.certidoes.portal_catalog import PORTAIS, cliente_payload
from app.certidoes.declaracoes import (
    endereco_completo_cliente,
    gerar_declaracao,
    localidade_cliente,
)
from flask import jsonify, make_response

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


@certidoes_bp.route("/api/cliente/<int:cliente_id>/autofill")
@login_required
def payload_autofill(cliente_id):
    """Retorna apenas os dados necessários ao preenchimento assistido."""
    cliente = Cliente.query.get_or_404(cliente_id)
    return jsonify({"cliente": cliente_payload(cliente), "portais": PORTAIS})


def _contexto_formulario_residencia(cliente, dados=None):
    dados_salvos = cliente.dados_declaracao_residencia
    valores = {
        "proprietario_nome": dados_salvos.proprietario_nome if dados_salvos else "",
        "proprietario_documento": dados_salvos.proprietario_documento if dados_salvos else "",
        "proprietario_rg": dados_salvos.proprietario_rg if dados_salvos else "",
        "proprietario_rg_emissor": dados_salvos.proprietario_rg_emissor if dados_salvos else "",
        "proprietario_endereco": dados_salvos.proprietario_endereco if dados_salvos else "",
        "cliente_endereco": (
            dados_salvos.cliente_endereco if dados_salvos
            else endereco_completo_cliente(cliente)
        ),
        "vinculo": dados_salvos.vinculo if dados_salvos else "",
        "local": dados_salvos.local if dados_salvos else localidade_cliente(cliente),
    }
    if dados:
        valores.update(dados)
    return render_template(
        "certidoes/declaracao_residencia_form.html",
        cliente=cliente,
        dados=valores,
        dados_salvos=bool(dados_salvos),
    )


@certidoes_bp.route(
    "/cliente/<int:cliente_id>/declaracao/residencia",
    methods=["GET", "POST"],
)
@login_required
def preparar_declaracao_residencia(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == "GET":
        return _contexto_formulario_residencia(cliente)

    labels = {
        "proprietario_nome": "nome do proprietário/declarante",
        "proprietario_documento": "CPF do proprietário/declarante",
        "proprietario_rg": "RG do proprietário/declarante",
        "proprietario_rg_emissor": "órgão emissor do RG",
        "proprietario_endereco": "endereço residencial da pessoa declarante",
        "cliente_endereco": "endereço onde o cliente reside",
        "vinculo": "vínculo com o cliente",
    }
    limites = {
        "proprietario_nome": 180,
        "proprietario_documento": 30,
        "proprietario_rg": 50,
        "proprietario_rg_emissor": 50,
        "proprietario_endereco": 400,
        "cliente_endereco": 400,
        "vinculo": 100,
        "local": 120,
    }
    dados = {
        campo: (request.form.get(campo) or "").strip()
        for campo in limites
    }
    campos_vazios = [labels[campo] for campo in labels if not dados[campo]]
    campos_longos = [campo for campo, limite in limites.items() if len(dados[campo]) > limite]

    if campos_vazios or campos_longos:
        if campos_vazios:
            flash("Preencha estes campos: " + ", ".join(campos_vazios) + ".", "warning")
        if campos_longos:
            flash("Alguns campos excedem o tamanho permitido. Revise os dados e tente novamente.", "warning")
        return _contexto_formulario_residencia(cliente, dados), 400

    registro = cliente.dados_declaracao_residencia
    if registro is None:
        registro = DadosDeclaracaoResidencia(cliente_id=cliente.id)
        db.session.add(registro)
    for campo in limites:
        setattr(registro, campo, dados[campo])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Falha ao salvar dados da declaração de residência do cliente %s",
            cliente.id,
        )
        flash("Não foi possível salvar os dados da declaração. Revise e tente novamente.", "danger")
        return _contexto_formulario_residencia(cliente, dados), 500

    try:
        pdf = gerar_declaracao(cliente, "residencia", dados=dados)
    except ValueError:
        return jsonify({"error": "Tipo de declaração inválido."}), 400
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="declaracao_residencia_{cliente.id}.pdf"'
    return response


@certidoes_bp.route("/cliente/<int:cliente_id>/declaracao/<tipo>.pdf")
@login_required
def baixar_declaracao(cliente_id, tipo):
    cliente = Cliente.query.get_or_404(cliente_id)
    if tipo == "residencia":
        return redirect(url_for("certidoes.preparar_declaracao_residencia", cliente_id=cliente.id))
    if tipo != "nao_inquerito":
        return jsonify({"error": "Tipo de declaração inválido."}), 400
    try:
        pdf = gerar_declaracao(cliente, tipo)
    except ValueError:
        return jsonify({"error": "Tipo de declaração inválido."}), 400
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="declaracao_nao_inquerito_{cliente.id}.pdf"'
    return response
