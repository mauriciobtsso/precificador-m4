from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app.extensions import db
from app.models import ModeloDocumento
from app.admin import admin_bp


_DECLARACOES_PADRAO = [
    ("Declaração de Residência", "declaracao_residencia", "Eu, <b>{{ cliente.nome }}</b>, inscrito(a) no CPF/CNPJ sob o nº <b>{{ cliente.documento }}</b>, declaro, para os devidos fins, que resido no endereço <b>{{ cliente.endereco_completo }}</b>. Declaro ainda que as informações acima são verdadeiras, estando ciente das responsabilidades legais decorrentes da falsidade desta declaração."),
    ("Declaração de Não Responder a Inquérito Policial", "declaracao_nao_inquerito", "Eu, <b>{{ cliente.nome }}</b>, inscrito(a) no CPF/CNPJ sob o nº <b>{{ cliente.documento }}</b>, declaro, para os devidos fins, que não estou respondendo a inquérito policial, salvo se expressamente informado em documento próprio. Declaro que as informações prestadas são verdadeiras e assumo responsabilidade por seu conteúdo."),
]


def _garantir_modelos_declaracoes():
    for titulo, chave, conteudo in _DECLARACOES_PADRAO:
        if not ModeloDocumento.query.filter_by(chave=chave).first():
            db.session.add(ModeloDocumento(titulo=titulo, chave=chave, conteudo=conteudo))
    db.session.commit()

@admin_bp.route("/documentos")
@login_required
def documentos():
    _garantir_modelos_declaracoes()
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
