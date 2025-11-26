from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app.extensions import db
from app.models import ModeloDocumento
from app.admin import admin_bp

@admin_bp.route("/documentos")
@login_required
def documentos():
    modelos = ModeloDocumento.query.order_by(ModeloDocumento.titulo).all()
    return render_template("admin/documentos.html", modelos=modelos)

@admin_bp.route("/documentos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_documento(id):
    modelo = ModeloDocumento.query.get_or_404(id)
    
    if request.method == "POST":
        modelo.titulo = request.form.get("titulo")
        modelo.conteudo = request.form.get("conteudo")
        db.session.commit()
        flash(f"Modelo '{modelo.titulo}' atualizado com sucesso.", "success")
        return redirect(url_for("admin.documentos"))
        
    return render_template("admin/documento_form.html", modelo=modelo)

# Variáveis disponíveis para ajuda na edição
@admin_bp.context_processor
def inject_vars():
    return dict(variaveis_disponiveis=[
        "{{ venda.id }}", "{{ venda.data_abertura }}", "{{ venda.valor_total }}",
        "{{ cliente.nome }}", "{{ cliente.documento }}", "{{ cliente.rg }}",
        "{{ cliente.endereco_completo }}", "{{ cliente.email }}", "{{ cliente.telefone }}",
        "{{ empresa.razao_social }}", "{{ empresa.cnpj }}", "{{ empresa.endereco }}",
        "{{ itens_lista }}"
    ])