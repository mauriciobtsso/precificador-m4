import os
import re
import unicodedata
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.produtos.models import Produto
from app.loja_admin import loja_admin_bp
from app.loja.models_admin import Banner, PaginaInstitucional
from app.models import Configuracao
from app.extensions import db
from app.utils.r2_helpers import upload_file_to_r2, gerar_link_r2
from werkzeug.utils import secure_filename
from . import loja_admin_bp


def slugify(text):
    """Converte Títulos em URLs amigáveis (Ex: 'Quem Somos' -> 'quem-somos')"""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

@loja_admin_bp.app_context_processor
def inject_helpers():
    return dict(gerar_link=gerar_link_r2)

@loja_admin_bp.route('/')
@login_required
def index():
    total_banners = Banner.query.count()
    total_paginas = PaginaInstitucional.query.count()
    return render_template('loja_admin/index.html', total_banners=total_banners, total_paginas=total_paginas)

# =========================================================
# GERENCIAR BANNERS (LISTAGEM, CRIAÇÃO E EDIÇÃO)
# =========================================================

@loja_admin_bp.route('/banners')
@login_required
def banners():
    lista_banners = Banner.query.order_by(Banner.ordem.asc()).all()
    return render_template('loja_admin/banners/lista.html', banners=lista_banners)

@loja_admin_bp.route('/banners/novo', methods=['GET', 'POST'])
@loja_admin_bp.route('/banners/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def gerenciar_banner(id=None):
    # Se houver ID, estamos editando; caso contrário, criando um novo
    banner = Banner.query.get(id) if id else Banner()
    
    if request.method == 'POST':
        banner.titulo = request.form.get('titulo')
        banner.link_destino = request.form.get('link_destino')
        banner.ordem = request.form.get('ordem', 0, type=int)
        banner.ativo = 'ativo' in request.form # Captura o switch do HTML
        
        arquivo = request.files.get('imagem')

        # Lógica de Upload
        if arquivo and arquivo.filename != '':
            # Se já existia uma imagem, o upload_file_to_r2 cuidará da nova
            # mas você pode implementar a exclusão da antiga se desejar.
            imagem_key = upload_file_to_r2(arquivo, folder="loja/banners")
            if imagem_key:
                banner.imagem_url = imagem_key
        
        # Validação para novos banners (imagem obrigatória no primeiro upload)
        if not banner.imagem_url:
            flash("❌ Erro: Um banner precisa de uma imagem.", "danger")
            return render_template('loja_admin/banners/form.html', banner=banner)

        if not id:
            db.session.add(banner)
        
        db.session.commit()
        
        # 🚀 LIMPEZA DE CACHE TÁTICA
        # Limpa o cache da home para o novo banner aparecer imediatamente
        from app.loja.routes import cache
        cache.delete('banners_home')
        cache.delete('index_v7') # Versão que configuramos no routes.py
        
        flash(f"Banner {'atualizado' if id else 'publicado'} com sucesso!", "success")
        return redirect(url_for('loja_admin.banners'))

    return render_template('loja_admin/banners/form.html', banner=banner)


@loja_admin_bp.route('/banners/excluir/<int:id>')
@login_required
def excluir_banner(id):
    banner = Banner.query.get_or_404(id)
    
    # Opcional: deletar o arquivo físico no R2 antes de apagar o registro
    # delete_file_from_r2(banner.imagem_url) 

    db.session.delete(banner)
    db.session.commit()
    
    # Limpa cache após exclusão
    from app.loja.routes import cache
    cache.delete('banners_home')
    
    flash("Banner removido do arsenal!", "success")
    return redirect(url_for('loja_admin.banners'))

# =========================================================
# GERENCIAR PÁGINAS (CRUD COMPLETO COM EDITOR RICO)
# =========================================================
@loja_admin_bp.route('/paginas')
@login_required
def paginas():
    lista_paginas = PaginaInstitucional.query.order_by(PaginaInstitucional.updated_at.desc()).all()
    return render_template('loja_admin/paginas/lista.html', paginas=lista_paginas)

@loja_admin_bp.route('/paginas/nova', methods=['GET', 'POST'])
@login_required
def nova_pagina():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        nova = PaginaInstitucional(
            titulo=titulo,
            slug=slugify(titulo),
            conteudo=request.form.get('conteudo'),
            visivel_rodape='visivel_rodape' in request.form
        )
        db.session.add(nova)
        db.session.commit()
        flash("Página criada com sucesso!", "success")
        return redirect(url_for('loja_admin.paginas'))
    return render_template('loja_admin/paginas/form.html', pagina=None)

@loja_admin_bp.route('/paginas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_pagina(id):
    pagina = PaginaInstitucional.query.get_or_404(id)
    if request.method == 'POST':
        pagina.titulo = request.form.get('titulo')
        pagina.conteudo = request.form.get('conteudo')
        pagina.visivel_rodape = 'visivel_rodape' in request.form
        pagina.slug = slugify(pagina.titulo)
        db.session.commit()
        flash("Página atualizada!", "success")
        return redirect(url_for('loja_admin.paginas'))
    return render_template('loja_admin/paginas/form.html', pagina=pagina)

@loja_admin_bp.route('/paginas/excluir/<int:id>')
@login_required
def excluir_pagina(id):
    pagina = PaginaInstitucional.query.get_or_404(id)
    db.session.delete(pagina)
    db.session.commit()
    flash("Página excluída!", "success")
    return redirect(url_for('loja_admin.paginas'))

# =========================================================
# CONFIGURAÇÕES DA LOJA (VERSÃO INTELIGENTE: CRIA CHAVES NOVAS)
# =========================================================
@loja_admin_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    if request.method == 'POST':
        # 1. Pegamos tudo o que veio do formulário (chaves e valores)
        for chave, valor in request.form.items():
            # Filtramos apenas chaves que comecem com 'loja_' para segurança
            if chave.startswith('loja_'):
                # Tenta encontrar a configuração no banco
                config = Configuracao.query.filter_by(chave=chave).first()
                
                if config:
                    # Se existe, apenas atualiza o valor
                    config.valor = valor
                else:
                    # Se não existe (como as chaves do banner), CRIA UMA NOVA
                    nova_config = Configuracao(chave=chave, valor=valor)
                    db.session.add(nova_config)
        
        try:
            db.session.commit()
            flash("✅ Todas as alterações e novas chaves foram salvas!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Erro ao salvar: {str(e)}", "danger")
            
        return redirect(url_for('loja_admin.configuracoes'))
    
    # Busca todas as configs atuais para exibir na lista
    configs = Configuracao.query.filter(Configuracao.chave.like('loja_%')).all()
    return render_template('loja_admin/configuracoes.html', configs=configs)

@loja_admin_bp.route('/auditoria-loja')
@login_required
def auditoria_loja():
    # ... (toda a lógica da query que já fizemos)
    produtos_incompletos = Produto.query.filter(
        or_(
            Produto.nome_comercial == None, Produto.nome_comercial == '',
            Produto.slug == None, Produto.slug == '',
            Produto.descricao_comercial == None, Produto.descricao_comercial == '',
            Produto.descricao_longa == None, Produto.descricao_longa == '',
            Produto.meta_title == None, Produto.meta_title == '',
            Produto.meta_description == None, Produto.meta_description == ''
        )
    ).order_by(Produto.nome.asc()).all()

    # O erro estava aqui: este 'return' deve ter 4 espaços (ou 1 tab) de recuo
    return render_template('auditoria_loja.html', produtos=produtos_incompletos, total=len(produtos_incompletos))

# =========================================================
# INTEGRAÇÕES (Melhor Envio, Pagar.me, SMTP)
# =========================================================

CHAVES_INTEGRACAO = [
    'integ_melhorenvio_token',
    'integ_melhorenvio_cep_origem',
    'integ_melhorenvio_sandbox',
    'integ_pagarme_secret_key',
    'integ_pagarme_public_key',
    'integ_pagarme_sandbox',
    'integ_smtp_host',
    'integ_smtp_port',
    'integ_smtp_from',
    'integ_smtp_user',
    'integ_smtp_password',
]

@loja_admin_bp.route('/integracoes', methods=['GET'])
@login_required
def integracoes():
    """Página de configuração de integrações externas."""
    config_objs = Configuracao.query.filter(
        Configuracao.chave.in_(CHAVES_INTEGRACAO)
    ).all()
    configs = {c.chave: c.valor for c in config_objs}
    return render_template('loja_admin/integracoes.html', configs=configs)


@loja_admin_bp.route('/integracoes/salvar', methods=['POST'])
@login_required
def salvar_integracoes():
    """Salva as credenciais de integração no banco (tabela Configuracao)."""
    checkboxes = {
        'integ_melhorenvio_sandbox',
        'integ_pagarme_sandbox',
    }

    for chave in CHAVES_INTEGRACAO:
        if chave in checkboxes:
            valor = '1' if chave in request.form else '0'
        else:
            valor = request.form.get(chave, '').strip()

        config = Configuracao.query.filter_by(chave=chave).first()
        if config:
            config.valor = valor
        else:
            db.session.add(Configuracao(chave=chave, valor=valor))

    try:
        db.session.commit()
        flash('✅ Integrações salvas com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erro ao salvar: {str(e)}', 'danger')

    return redirect(url_for('loja_admin.integracoes'))


@loja_admin_bp.route('/integracoes/testar', methods=['POST'])
@login_required
def testar_integracao():
    """Testa a conexão com um serviço externo (usado pelo botão Testar no front)."""
    import requests as req_lib

    data = request.get_json()
    servico = data.get('servico')

    if servico == 'melhorenvio':
        token = Configuracao.query.filter_by(chave='integ_melhorenvio_token').first()
        sandbox = Configuracao.query.filter_by(chave='integ_melhorenvio_sandbox').first()

        if not token or not token.valor:
            return jsonify({"success": False, "message": "Token não configurado."})

        base = "https://sandbox.melhorenvio.com.br" if (sandbox and sandbox.valor == '1') else "https://www.melhorenvio.com.br"
        url = f"{base}/api/v2/me"

        try:
            resp = req_lib.get(url, headers={
                "Authorization": f"Bearer {token.valor}",
                "Accept": "application/json",
                "User-Agent": "M4 Tatica (contato@m4tatica.com.br)"
            }, timeout=8)

            if resp.status_code == 200:
                user = resp.json()
                nome = user.get('firstname', '') + ' ' + user.get('lastname', '')
                return jsonify({"success": True, "message": f"Autenticado como: {nome.strip()}"})
            else:
                return jsonify({"success": False, "message": f"HTTP {resp.status_code} — verifique o token."})

        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

    return jsonify({"success": False, "message": "Serviço não reconhecido."})