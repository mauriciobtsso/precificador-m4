# app/loja/routes_auth.py
import os
from datetime import date
from urllib.parse import urlparse, urljoin
from flask import render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from app import db
from app.loja import loja_bp
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente, Documento, Arma
from app.loja.auth_loja import logar_cliente, deslogar_cliente, get_cliente_logado, cliente_logado_required
from app.utils.datetime import now_local
from app.extensions import limiter

# 🛠️ Storage tático M4: uploads do cliente agora vão direto pro R2,
# nunca mais para o disco local (que é efêmero no Render).
from app.utils.r2_helpers import upload_file_to_r2, gerar_link_r2
from app.utils.storage import deletar_arquivo

EXTENSOES_OK  = {'pdf', 'jpg', 'jpeg', 'png'}
CATEGORIA_LOJA = 'cliente_loja'

# Assinaturas (magic bytes) dos tipos de arquivo permitidos
_MAGIC = {
    b'%PDF':         'pdf',
    b'\xff\xd8\xff': 'jpg',
    b'\x89PNG':      'png',
}


def _ext_ok(nome: str) -> bool:
    return '.' in nome and nome.rsplit('.', 1)[1].lower() in EXTENSOES_OK


def _magic_ok(fileobj) -> bool:
    """Verifica a assinatura real dos primeiros bytes do arquivo."""
    header = fileobj.read(8)
    fileobj.seek(0)          # reposiciona para o upload não ficar vazio
    for magic in _MAGIC:
        if header.startswith(magic):
            return True
    return False


def _parse_date(campo):
    val = (request.form.get(campo) or '').strip()
    try:
        return date.fromisoformat(val) if val else None
    except ValueError:
        return None


def _is_safe_url(target: str) -> bool:
    """Valida que o redirect 'next' aponta apenas para o próprio domínio."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ('http', 'https')
        and ref_url.netloc == test_url.netloc
    )


def _validar_cpf(cpf: str) -> bool:
    """Valida o algoritmo oficial do CPF."""
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i + 1) - num) for num in range(i))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True


def _validar_email(email: str) -> bool:
    """Valida formato básico de e-mail."""
    import re
    regex = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    return bool(re.match(regex, email.lower()))


# ──────────────────────────────────────────────────────────────────
# CONTEXT PROCESSOR
# ──────────────────────────────────────────────────────────────────
@loja_bp.app_context_processor
def inject_cliente_loja():
    return {'cliente_loja': get_cliente_logado()}


# ──────────────────────────────────────────────────────────────────
# LOGIN / CADASTRO / LOGOUT
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", error_message="Muitas tentativas de login. Aguarde 1 minuto.")
def login():
    if get_cliente_logado():
        return redirect(url_for('loja.minha_conta'))
    if request.method == 'POST':
        email  = (request.form.get('email') or '').strip().lower()
        senha  = request.form.get('password') or ''
        cliente = Cliente.query.filter_by(email_login=email).first()
        if not cliente:
            flash('E-mail não encontrado.', 'danger')
        elif not cliente.ativo_loja:
            flash('Conta desativada. Entre em contato com a loja.', 'danger')
        elif not cliente.check_senha(senha):
            flash('Senha incorreta.', 'danger')
        else:
            logar_cliente(cliente)
            flash(f'Bem-vindo, {cliente.nome.split()[0]}!', 'success')
            next_url = request.args.get('next')
            if _is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for('loja.minha_conta'))
    return render_template('loja/auth/login.html')


@loja_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if get_cliente_logado():
        return redirect(url_for('loja.minha_conta'))
    if request.method == 'POST':
        nome     = (request.form.get('nome') or '').strip()
        email    = (request.form.get('email') or '').strip().lower()
        cpf      = (request.form.get('documento') or '').strip()
        senha    = request.form.get('password') or ''
        confirma = request.form.get('password_confirm') or ''
        if not nome or not email or not cpf or not senha:
            flash('Preencha todos os campos obrigatórios.', 'warning')
            return render_template('loja/auth/cadastro.html')
        
        # Validações de Segurança M4
        if not _validar_email(email):
            flash('Por favor, informe um e-mail válido.', 'warning')
            return render_template('loja/auth/cadastro.html')
        
        if not _validar_cpf(cpf):
            flash('O CPF informado é inválido.', 'warning')
            return render_template('loja/auth/cadastro.html')

        if len(senha) < 8:
            flash('A senha deve ter pelo menos 8 caracteres.', 'warning')
            return render_template('loja/auth/cadastro.html')
        
        if senha != confirma:
            flash('As senhas não coincidem.', 'warning')
            return render_template('loja/auth/cadastro.html')
            
        if Cliente.query.filter_by(email_login=email).first():
            flash('Este e-mail já está cadastrado.', 'warning')
            return render_template('loja/auth/cadastro.html')
            
        cpf_digits = ''.join(filter(str.isdigit, cpf))
        cliente = Cliente.query.filter_by(documento=cpf_digits).first() if cpf_digits else None
        if cliente:
            if cliente.email_login:
                flash('Este CPF já possui uma conta na loja.', 'warning')
                return render_template('loja/auth/cadastro.html')
            cliente.email_login    = email
            cliente.loja_criado_em = now_local()
        else:
            cliente = Cliente(
                nome=nome, documento=cpf_digits or None,
                email_login=email, ativo_loja=True,
                loja_criado_em=now_local(),
                created_at=now_local(), updated_at=now_local(),
            )
            db.session.add(cliente)
            db.session.flush()
            db.session.add(ContatoCliente(cliente_id=cliente.id, tipo='email', valor=email))
        cliente.set_senha(senha)
        cliente.ativo_loja = True
        db.session.commit()
        
        # Envio de E-mail de Boas-vindas (Brevo)
        try:
            from app.utils.email_service import enviar_email_boas_vindas
            enviar_email_boas_vindas(cliente)
        except Exception as e:
            current_app.logger.error(f"Erro ao disparar e-mail de boas-vindas: {e}")

        logar_cliente(cliente)
        flash('Conta criada com sucesso! Bem-vindo.', 'success')
        return redirect(url_for('loja.minha_conta'))
    return render_template('loja/auth/cadastro.html')


@loja_bp.route('/logout')
def logout():
    deslogar_cliente()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('loja.index'))


# ──────────────────────────────────────────────────────────────────
# MINHA CONTA / PEDIDOS
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/minha-conta')
@cliente_logado_required
def minha_conta():
    return render_template('loja/cliente/dashboard.html')


@loja_bp.route('/meus-pedidos')
@cliente_logado_required
def meus_pedidos():
    cliente = get_cliente_logado()
    vendas  = sorted(cliente.vendas or [], key=lambda v: v.data_abertura, reverse=True)
    return render_template('loja/cliente/pedidos.html', vendas=vendas)


@loja_bp.route('/meus-pedidos/<int:venda_id>')
@cliente_logado_required
def detalhe_pedido(venda_id):
    from app.vendas.models import Venda
    cliente = get_cliente_logado()
    venda   = Venda.query.filter_by(id=venda_id, cliente_id=cliente.id).first_or_404()
    return render_template('loja/cliente/pedido_detalhe.html', venda=venda)


# ──────────────────────────────────────────────────────────────────
# ENDEREÇOS
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/meus-enderecos')
@cliente_logado_required
def meus_enderecos():
    cliente = get_cliente_logado()
    return render_template('loja/cliente/enderecos.html', enderecos=cliente.enderecos or [])


@loja_bp.route('/meus-enderecos/novo', methods=['POST'])
@cliente_logado_required
def novo_endereco():
    cliente = get_cliente_logado()
    db.session.add(EnderecoCliente(
        cliente_id  = cliente.id,
        tipo        = (request.form.get('tipo') or 'residencial').strip(),
        cep         = (request.form.get('cep') or '').strip(),
        logradouro  = (request.form.get('logradouro') or '').strip(),
        numero      = (request.form.get('numero') or '').strip(),
        complemento = (request.form.get('complemento') or '').strip() or None,
        bairro      = (request.form.get('bairro') or '').strip(),
        cidade      = (request.form.get('cidade') or '').strip(),
        estado      = (request.form.get('estado') or '').strip().upper(),
    ))
    db.session.commit()
    flash('Endereço adicionado!', 'success')
    return redirect(url_for('loja.meus_enderecos'))


@loja_bp.route('/meus-enderecos/<int:endereco_id>/editar', methods=['POST'])
@cliente_logado_required
def editar_endereco(endereco_id):
    cliente = get_cliente_logado()
    end = EnderecoCliente.query.filter_by(id=endereco_id, cliente_id=cliente.id).first_or_404()
    end.tipo        = (request.form.get('tipo') or 'residencial').strip()
    end.cep         = (request.form.get('cep') or '').strip()
    end.logradouro  = (request.form.get('logradouro') or '').strip()
    end.numero      = (request.form.get('numero') or '').strip()
    end.complemento = (request.form.get('complemento') or '').strip() or None
    end.bairro      = (request.form.get('bairro') or '').strip()
    end.cidade      = (request.form.get('cidade') or '').strip()
    end.estado      = (request.form.get('estado') or '').strip().upper()
    db.session.commit()
    flash('Endereço atualizado.', 'success')
    return redirect(url_for('loja.meus_enderecos'))


@loja_bp.route('/meus-enderecos/<int:endereco_id>/excluir', methods=['POST'])
@cliente_logado_required
def excluir_endereco(endereco_id):
    cliente = get_cliente_logado()
    end = EnderecoCliente.query.filter_by(id=endereco_id, cliente_id=cliente.id).first_or_404()
    db.session.delete(end)
    db.session.commit()
    flash('Endereço removido.', 'info')
    return redirect(url_for('loja.meus_enderecos'))


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — listar
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/meus-documentos')
@cliente_logado_required
def meus_documentos():
    cliente = get_cliente_logado()
    hoje    = date.today()

    todos_docs  = (Documento.query
                   .filter_by(cliente_id=cliente.id)
                   .order_by(Documento.created_at.desc())
                   .all())
    docs_cliente = [d for d in todos_docs if d.categoria == CATEGORIA_LOJA]
    docs_admin   = [d for d in todos_docs if d.categoria != CATEGORIA_LOJA]

    cr_vencido = bool(cliente.data_validade_cr and hoje > cliente.data_validade_cr)
    armas_info = [
        {
            'arma': arma,
            'craf_vencido': bool(
                arma.data_validade_craf
                and not arma.validade_indeterminada
                and hoje > arma.data_validade_craf
            )
        }
        for arma in (cliente.armas or [])
    ]

    return render_template(
        'loja/cliente/documentos.html',
        docs_cliente=docs_cliente,
        docs_admin=docs_admin,
        cr_vencido=cr_vencido,
        armas_info=armas_info,
    )


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — upload de documento genérico
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/meus-documentos/upload', methods=['POST'])
@cliente_logado_required
def upload_documento():
    cliente = get_cliente_logado()
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        flash('Selecione um arquivo.', 'warning')
        return redirect(url_for('loja.meus_documentos'))
    if not _ext_ok(arquivo.filename):
        flash('Formato não permitido. Use PDF, JPG ou PNG.', 'warning')
        return redirect(url_for('loja.meus_documentos'))
    if not _magic_ok(arquivo.stream):
        flash('Arquivo inválido: o conteúdo não corresponde ao formato declarado.', 'danger')
        return redirect(url_for('loja.meus_documentos'))

    # 🛰️ Nome único e envio direto para o R2 (bucket privado m4-clientes-docs).
    # Nada mais é salvo em disco local — o disco do Render é efêmero.
    nome_seguro = secure_filename(arquivo.filename)
    timestamp   = now_local().strftime('%Y%m%d%H%M%S')
    arquivo.filename = f"{timestamp}_{nome_seguro}"

    caminho_r2 = upload_file_to_r2(arquivo, folder=f"clientes/{cliente.id}/documentos")
    if not caminho_r2:
        flash('Erro ao enviar o arquivo para o storage. Tente novamente.', 'danger')
        return redirect(url_for('loja.meus_documentos'))

    indet = bool(request.form.get('validade_indeterminada'))
    db.session.add(Documento(
        cliente_id             = cliente.id,
        tipo                   = (request.form.get('tipo') or 'Outro').strip(),
        categoria              = CATEGORIA_LOJA,
        numero_documento       = (request.form.get('numero_documento') or '').strip() or None,
        data_emissao           = _parse_date('data_emissao'),
        data_validade          = None if indet else _parse_date('data_validade'),
        validade_indeterminada = indet,
        observacoes            = (request.form.get('observacoes') or '').strip() or None,
        nome_original          = nome_seguro,
        caminho_arquivo        = caminho_r2,
        mime_type              = arquivo.mimetype,
    ))
    db.session.commit()
    flash('Documento enviado com sucesso!', 'success')
    return redirect(url_for('loja.meus_documentos'))


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — excluir (só os do próprio cliente)
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/meus-documentos/<int:doc_id>/excluir', methods=['POST'])
@cliente_logado_required
def excluir_documento(doc_id):
    cliente = get_cliente_logado()
    doc = Documento.query.filter_by(
        id=doc_id, cliente_id=cliente.id, categoria=CATEGORIA_LOJA
    ).first_or_404()

    caminho_para_deletar = doc.caminho_arquivo

    db.session.delete(doc)
    db.session.commit()

    # 🛰️ Exclusão no R2 (não é mais arquivo local)
    if caminho_para_deletar:
        deletar_arquivo(caminho_para_deletar)

    flash('Documento removido.', 'info')
    return redirect(url_for('loja.meus_documentos'))


# ──────────────────────────────────────────────────────────────────
# DOCUMENTOS — download
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/meus-documentos/<int:doc_id>/baixar')
@cliente_logado_required
def baixar_documento(doc_id):
    cliente = get_cliente_logado()
    doc = Documento.query.filter_by(id=doc_id, cliente_id=cliente.id).first_or_404()

    if not doc.caminho_arquivo:
        flash('Arquivo não encontrado.', 'danger')
        return redirect(url_for('loja.meus_documentos'))

    # 🛰️ Gera link assinado do R2 em vez de servir arquivo local
    link = gerar_link_r2(doc.caminho_arquivo)
    if not link:
        flash('Erro ao gerar o link do arquivo.', 'danger')
        return redirect(url_for('loja.meus_documentos'))

    return redirect(link)


# ──────────────────────────────────────────────────────────────────
# ARMAS — solicitar registro
#
# Campos reais do modelo Arma (sem 'observacoes'):
#   tipo, funcionamento, marca, modelo, calibre, numero_serie,
#   emissor_craf, numero_sigma, categoria_adquirente,
#   validade_indeterminada, data_validade_craf, caminho_craf,
#   data_aquisicao
#
# O arquivo do CRAF é salvo em caminho_craf (campo existente).
# O form deve ser multipart/form-data para aceitar o arquivo.
# ──────────────────────────────────────────────────────────────────
@loja_bp.route('/meus-documentos/solicitar-arma', methods=['POST'])
@cliente_logado_required
def solicitar_arma():
    cliente = get_cliente_logado()

    # ── arquivo do CRAF (opcional) — agora enviado direto pro R2 ──
    caminho_craf = None
    arquivo_craf = request.files.get('arquivo_craf')
    if arquivo_craf and arquivo_craf.filename:
        if not _ext_ok(arquivo_craf.filename):
            flash('Formato do arquivo CRAF inválido. Use PDF, JPG ou PNG.', 'warning')
            return redirect(url_for('loja.meus_documentos'))
        if not _magic_ok(arquivo_craf.stream):
            flash('Arquivo CRAF inválido: o conteúdo não corresponde ao formato declarado.', 'danger')
            return redirect(url_for('loja.meus_documentos'))

        nome_seguro_craf = secure_filename(arquivo_craf.filename)
        timestamp_craf   = now_local().strftime('%Y%m%d%H%M%S')
        arquivo_craf.filename = f"craf_{timestamp_craf}_{nome_seguro_craf}"

        caminho_craf = upload_file_to_r2(arquivo_craf, folder=f"clientes/{cliente.id}/armas")
        if not caminho_craf:
            flash('Erro ao enviar o arquivo do CRAF para o storage. Tente novamente.', 'danger')
            return redirect(url_for('loja.meus_documentos'))

    # ── número de série — evita violação de unique=True ─────────
    numero_serie = (request.form.get('numero_serie') or '').strip() or None
    if numero_serie and Arma.query.filter_by(numero_serie=numero_serie).first():
        flash(f'Já existe uma arma cadastrada com o nº de série "{numero_serie}". Verifique os dados.', 'warning')
        return redirect(url_for('loja.meus_documentos'))

    indet = bool(request.form.get('validade_indeterminada'))

    # ── cria o registro usando apenas os campos que existem no modelo ──
    arma = Arma(
        cliente_id             = cliente.id,
        tipo                   = (request.form.get('tipo') or '').strip() or None,
        funcionamento          = (request.form.get('funcionamento') or '').strip() or None,
        marca                  = (request.form.get('marca') or '').strip() or None,
        modelo                 = (request.form.get('modelo') or '').strip() or None,
        calibre                = (request.form.get('calibre') or '').strip() or None,
        numero_serie           = numero_serie,
        emissor_craf           = (request.form.get('emissor_craf') or '').strip() or None,
        numero_sigma           = (request.form.get('numero_sigma') or '').strip() or None,
        data_aquisicao         = _parse_date('data_aquisicao'),
        validade_indeterminada = indet,
        data_validade_craf     = None if indet else _parse_date('data_validade_craf'),
        caminho_craf           = caminho_craf,   # chave R2 do CRAF (ou None)
    )

    db.session.add(arma)
    db.session.commit()

    flash('Arma registrada com sucesso! Nossa equipe irá verificar os dados em breve.', 'success')
    return redirect(url_for('loja.meus_documentos'))
