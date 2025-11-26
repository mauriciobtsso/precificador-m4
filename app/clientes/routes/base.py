from flask import (
    render_template, request, redirect, url_for,
    flash, jsonify, current_app
)

from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, aliased

from app import db
from app.utils.datetime import now_local
from app.utils.db_helpers import get_or_404

from app.clientes import clientes_bp
from app.clientes.models import (
    Cliente, Documento, Arma, Comunicacao, Processo,
    EnderecoCliente, ContatoCliente
)

from app.clientes.constants import (
    TIPOS_ARMA, FUNCIONAMENTO_ARMA, EMISSORES_CRAF,
    CATEGORIAS_ADQUIRENTE, CATEGORIAS_DOCUMENTO,
    EMISSORES_DOCUMENTO
)

from datetime import datetime


# -------------------------------------------------
# Helper local — será movido depois para helpers.py
# -------------------------------------------------
def parse_date(value):
    """Converte 'YYYY-MM-DD' ou 'DD/MM/YYYY' para date (ou None)."""
    if not value or not str(value).strip():
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


# =================================================
# LISTAR CLIENTES
# =================================================
@clientes_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()

    # Subqueries de telefone e email principal
    tel_sq = (
        db.session.query(
            ContatoCliente.cliente_id,
            ContatoCliente.valor.label("telefone_principal"),
            func.row_number().over(
                partition_by=ContatoCliente.cliente_id,
                order_by=ContatoCliente.id
            ).label("rn")
        )
        .filter(func.lower(ContatoCliente.tipo).in_(["telefone", "celular", "whatsapp"]))
        .subquery()
    )
    tel_alias = aliased(tel_sq)

    email_sq = (
        db.session.query(
            ContatoCliente.cliente_id,
            ContatoCliente.valor.label("email_principal"),
            func.row_number().over(
                partition_by=ContatoCliente.cliente_id,
                order_by=ContatoCliente.id
            ).label("rn")
        )
        .filter(func.lower(ContatoCliente.tipo) == "email")
        .subquery()
    )
    email_alias = aliased(email_sq)

    # Query principal
    query = (
        db.session.query(
            Cliente,
            tel_alias.c.telefone_principal,
            email_alias.c.email_principal,
        )
        .outerjoin(tel_alias, (Cliente.id == tel_alias.c.cliente_id) & (tel_alias.c.rn == 1))
        .outerjoin(email_alias, (Cliente.id == email_alias.c.cliente_id) & (email_alias.c.rn == 1))
        .group_by(Cliente.id, tel_alias.c.telefone_principal, email_alias.c.email_principal)
    )

    # Filtros
    if q:
        q_digits = "".join(filter(str.isdigit, q))

        search_filter = or_(
            Cliente.nome.ilike(f"%{q}%"),
            Cliente.documento.ilike(f"%{q}%"),
            tel_alias.c.telefone_principal.ilike(f"%{q}%"),
            email_alias.c.email_principal.ilike(f"%{q}%"),
        )

        if q_digits:
            search_filter = or_(
                search_filter,
                func.replace(
                    func.replace(func.replace(Cliente.documento, ".", ""), "-", ""), "/", ""
                ).ilike(f"%{q_digits}%")
            )
            search_filter = or_(
                search_filter,
                func.replace(
                    func.replace(
                        func.replace(
                            func.replace(tel_alias.c.telefone_principal, "(", ""), ")", ""
                        ),
                        "-",
                        ""
                    ),
                    " ",
                    ""
                ).ilike(f"%{q_digits}%")
            )

        query = query.filter(search_filter)

    clientes_pagination = (
        query.order_by(Cliente.id)
        .distinct(Cliente.id)
        .order_by(Cliente.nome.asc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    # Constrói lista final
    clientes_list = []
    for cliente, telefone, email in clientes_pagination.items:
        cliente.telefone_principal = telefone
        cliente.email_principal = email
        clientes_list.append(cliente)

    # AJAX
    if request.args.get("ajax"):
        return render_template(
            "clientes/index.html",
            clientes=clientes_list,
            pagination=clientes_pagination,
            q=q,
            _partial=True
        )

    return render_template(
        "clientes/index.html",
        clientes=clientes_list,
        pagination=clientes_pagination,
        q=q,
    )


# =================================================
# NOVO CLIENTE
# =================================================
@clientes_bp.route("/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        try:
            documento = request.form.get("documento")

            if documento:
                existente = Cliente.query.filter_by(documento=documento).first()
                if existente:
                    flash("Já existe um cliente cadastrado com este CPF/CNPJ.", "warning")
                    return redirect(url_for("clientes.cliente_detalhe", cliente_id=existente.id))

            cliente = Cliente(
                nome=request.form.get("nome"),
                apelido=request.form.get("apelido"),
                razao_social=request.form.get("razao_social"),
                sexo=request.form.get("sexo"),
                data_nascimento=parse_date(request.form.get("data_nascimento")),
                profissao=request.form.get("profissao"),
                estado_civil=request.form.get("estado_civil"),
                escolaridade=request.form.get("escolaridade"),
                nome_pai=request.form.get("nome_pai"),
                nome_mae=request.form.get("nome_mae"),
                documento=documento,
                cac=bool(request.form.get("cac")),
                filiado=bool(request.form.get("filiado")),
                policial=bool(request.form.get("policial")),
                bombeiro=bool(request.form.get("bombeiro")),
                militar=bool(request.form.get("militar")),
                iat=bool(request.form.get("iat")),
                psicologo=bool(request.form.get("psicologo")),
                created_at=now_local(),
                updated_at=now_local(),
            )

            db.session.add(cliente)
            db.session.flush()

            # Endereço principal
            cep = request.form.get("cep")
            endereco = request.form.get("endereco")
            numero = request.form.get("numero")
            bairro = request.form.get("bairro")
            cidade = request.form.get("cidade")
            estado = request.form.get("estado")

            if any([cep, endereco, bairro, cidade, estado]):
                end = EnderecoCliente(
                    cliente_id=cliente.id,
                    tipo="residencial",
                    cep=cep,
                    logradouro=endereco,
                    numero=numero,
                    complemento=request.form.get("complemento"),
                    bairro=bairro,
                    cidade=cidade,
                    estado=estado,
                )
                db.session.add(end)

            # Contatos
            email = request.form.get("email")
            telefone = request.form.get("telefone")
            celular = request.form.get("celular")

            if email:
                db.session.add(ContatoCliente(cliente_id=cliente.id, tipo="email", valor=email))
            if telefone:
                db.session.add(ContatoCliente(cliente_id=cliente.id, tipo="telefone", valor=telefone))
            if celular:
                db.session.add(ContatoCliente(cliente_id=cliente.id, tipo="celular", valor=celular))

            db.session.commit()
            flash("Cliente cadastrado com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar cliente: {e}", "danger")
            return redirect(url_for("clientes.novo_cliente"))

    return render_template("clientes/novo.html")


# =================================================
# DETALHE DO CLIENTE (CORRIGIDO)
# =================================================
@clientes_bp.route("/<int:cliente_id>")
def detalhe(cliente_id):
    try:
        cliente = (
            Cliente.query
            .options(
                joinedload(Cliente.enderecos),
                joinedload(Cliente.contatos),
                joinedload(Cliente.documentos),
                joinedload(Cliente.armas),
                joinedload(Cliente.comunicacoes),
                joinedload(Cliente.processos),
                joinedload(Cliente.vendas) # <--- ADICIONADO: Carrega as vendas
            )
            .get_or_404(cliente_id)
        )

        resumo = {
            "documentos": len(cliente.documentos or []),
            "armas": len(cliente.armas or []),
            "comunicacoes": len(cliente.comunicacoes or []),
            "processos": len(cliente.processos or []),
            "vendas": len(cliente.vendas or []), # <--- ADICIONADO: Contagem de vendas
        }

        # PARTE RESTAURADA QUE FALTAVA
        alertas = []
        if not cliente.cr:
            alertas.append("CR não informado.")

        timeline = []
        if cliente.comunicacoes:
            ultima_com = max(cliente.comunicacoes, key=lambda c: c.data)
            timeline.append({
                "data": ultima_com.data,
                "tipo": "Comunicação",
                "descricao": ultima_com.assunto,
            })

        return render_template(
            "clientes/detalhe.html",
            cliente=cliente,
            resumo=resumo,
            alertas=alertas,
            timeline=timeline,
            enderecos=cliente.enderecos,
            contatos=cliente.contatos,
            TIPOS_ARMA=TIPOS_ARMA,
            FUNCIONAMENTO_ARMA=FUNCIONAMENTO_ARMA,
            EMISSORES_CRAF=EMISSORES_CRAF,
            CATEGORIAS_ADQUIRENTE=CATEGORIAS_ADQUIRENTE,
            CATEGORIAS_DOCUMENTO=CATEGORIAS_DOCUMENTO,
            EMISSORES_DOCUMENTO=EMISSORES_DOCUMENTO,
        )
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar detalhe do cliente {cliente_id}: {e}")
        flash("Não foi possível carregar os dados do cliente.", "danger")
        return redirect(url_for("clientes.index"))


# =================================================
# EDITAR CLIENTE
# =================================================
@clientes_bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
def editar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        try:
            cliente.nome = request.form.get("nome") or None
            cliente.apelido = request.form.get("apelido") or None
            cliente.sexo = request.form.get("sexo") or None
            cliente.data_nascimento = parse_date(request.form.get("data_nascimento"))
            cliente.profissao = request.form.get("profissao") or None
            cliente.estado_civil = request.form.get("estado_civil") or None
            cliente.escolaridade = request.form.get("escolaridade") or None
            cliente.nome_pai = request.form.get("nome_pai") or None
            cliente.nome_mae = request.form.get("nome_mae") or None

            cliente.documento = request.form.get("documento") or None
            cliente.cr = request.form.get("cr") or None
            cliente.cr_emissor = request.form.get("cr_emissor") or None
            cliente.sigma = request.form.get("sigma") or None
            cliente.sinarm = request.form.get("sinarm") or None
            cliente.razao_social = request.form.get("razao_social") or None

            # Endereço
            cep = request.form.get("cep")
            logradouro = request.form.get("endereco")
            numero = request.form.get("numero")
            complemento = request.form.get("complemento")
            bairro = request.form.get("bairro")
            cidade = request.form.get("cidade")
            estado = request.form.get("estado")

            if cliente.enderecos and len(cliente.enderecos) > 0:
                end = cliente.enderecos[0]
            else:
                end = EnderecoCliente(cliente_id=cliente.id)
                db.session.add(end)

            end.cep = cep or None
            end.logradouro = logradouro or None
            end.numero = numero or None
            end.complemento = complemento or None
            end.bairro = bairro or None
            end.cidade = cidade or None
            end.estado = estado or None
            end.tipo = "residencial"

            # Contatos
            email_val = request.form.get("email")
            tel_val = request.form.get("telefone")
            cel_val = request.form.get("celular")

            tipos = {"email": email_val, "telefone": tel_val, "celular": cel_val}

            for tipo, valor in tipos.items():
                if not valor:
                    continue
                contato_existente = next((c for c in cliente.contatos if c.tipo == tipo), None)
                if contato_existente:
                    contato_existente.valor = valor
                else:
                    db.session.add(ContatoCliente(cliente_id=cliente.id, tipo=tipo, valor=valor))

            # Flags
            cliente.cac = "cac" in request.form
            cliente.filiado = "filiado" in request.form
            cliente.policial = "policial" in request.form
            cliente.bombeiro = "bombeiro" in request.form
            cliente.militar = "militar" in request.form
            cliente.iat = "iat" in request.form
            cliente.psicologo = "psicologo" in request.form
            cliente.atirador_n1 = "atirador_n1" in request.form
            cliente.atirador_n2 = "atirador_n2" in request.form
            cliente.atirador_n3 = "atirador_n3" in request.form

            cliente.updated_at = now_local()
            db.session.commit()

            flash("Dados do cliente atualizados com sucesso!", "success")
            return redirect(url_for("clientes.detalhe", cliente_id=cliente.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao editar cliente: {e}", "danger")

    return render_template("clientes/editar.html", cliente=cliente)


# =================================================
# EXCLUIR CLIENTE
# =================================================
@clientes_bp.route("/<int:cliente_id>/excluir", methods=["POST"])
def deletar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    try:
        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente excluído com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir cliente: {e}", "danger")

    return redirect(url_for("clientes.index"))