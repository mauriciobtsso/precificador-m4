import os
import re
import unicodedata
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required
from app.loja_admin import loja_admin_bp
from app.loja.models_admin import Banner, PaginaInstitucional
from app.models import Configuracao
from app.extensions import db
from app.utils.r2_helpers import upload_file_to_r2, gerar_link_r2
from werkzeug.utils import secure_filename

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
# GERENCIAR BANNERS
# =========================================================
@loja_admin_bp.route('/banners')
@login_required
def banners():
    lista_banners = Banner.query.order_by(Banner.ordem.asc()).all()
    return render_template('loja_admin/banners/lista.html', banners=lista_banners)

@loja_admin_bp.route('/banners/novo', methods=['GET', 'POST'])
@login_required
def novo_banner():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        link_destino = request.form.get('link_destino')
        ordem = request.form.get('ordem', 0)
        arquivo = request.files.get('imagem')

        if arquivo and arquivo.filename != '':
            imagem_key = upload_file_to_r2(arquivo, folder="loja/banners")
            if imagem_key:
                novo = Banner(titulo=titulo, imagem_url=imagem_key, link_destino=link_destino, ordem=ordem, ativo=True)
                db.session.add(novo)
                db.session.commit()
                flash("Banner publicado!", "success")
                return redirect(url_for('loja_admin.banners'))
    return render_template('loja_admin/banners/form.html')

@loja_admin_bp.route('/banners/excluir/<int:id>')
@login_required
def excluir_banner(id):
    banner = Banner.query.get_or_404(id)
    db.session.delete(banner)
    db.session.commit()
    flash("Banner removido!", "success")
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