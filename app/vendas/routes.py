from flask import render_template, request, jsonify, redirect, url_for, flash, render_template_string, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.vendas.models import Venda, ItemVenda, VendaAnexo
from app.clientes.models import Cliente, Arma
from app.produtos.models import Produto
from app.estoque.models import ItemEstoque
from app.services.venda_service import VendaService
from . import vendas_bp
import re
from datetime import datetime, timedelta
from sqlalchemy import extract, func

# Imports para Documentos e Uploads
from app.utils.format_helpers import br_money
from app.models import ModeloDocumento
from app.utils.r2_helpers import upload_file_to_r2

# ===============================================================
# TELAS (HTML)
# ===============================================================

@vendas_bp.route("/", methods=["GET", "POST"])
@login_required
def vendas():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    query = Venda.query.join(Cliente, isouter=True)

    # --- Filtros ---
    cliente_nome = request.args.get("cliente", "").strip()
    status = request.args.get("status", "").strip()
    periodo = request.args.get("periodo", "").strip()
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    if cliente_nome:
        query = query.filter(Cliente.nome.ilike(f"%{cliente_nome}%"))
    if status:
        query = query.filter(Venda.status.ilike(f"%{status}%"))

    hoje = datetime.today()
    if periodo == "7d":
        query = query.filter(Venda.data_abertura >= hoje - timedelta(days=7))
    elif periodo == "mes":
        query = query.filter(
            extract("year", Venda.data_abertura) == hoje.year,
            extract("month", Venda.data_abertura) == hoje.month
        )
    elif periodo == "personalizado" and data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Venda.data_abertura >= inicio, Venda.data_abertura < fim)
        except Exception:
            pass

    # --- Paginação ---
    vendas_paginadas = query.order_by(Venda.data_abertura.desc()).paginate(page=page, per_page=per_page)

    # --- Resumo agregado OTIMIZADO (SQL) ---
    resumo_dados = query.with_entities(
        func.count(Venda.id).label('total'),
        func.sum(Venda.valor_total).label('soma_total'),
        func.sum(Venda.desconto_valor).label('soma_descontos'),
        func.sum(Venda.valor_recebido).label('soma_recebido')
    ).first()

    total_vendas = resumo_dados.total or 0
    soma_total = resumo_dados.soma_total or 0
    soma_descontos = resumo_dados.soma_descontos or 0
    soma_recebido = resumo_dados.soma_recebido or 0
    
    media_venda = soma_total / total_vendas if total_vendas > 0 else 0

    resumo = {
        "total_vendas": total_vendas,
        "soma_total": soma_total,
        "soma_descontos": soma_descontos,
        "soma_recebido": soma_recebido,
        "media_venda": media_venda,
    }

    return render_template(
        "vendas/index.html",
        vendas=vendas_paginadas,
        resumo=resumo,
        cliente_nome=cliente_nome,
        status=status,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@vendas_bp.route("/<int:venda_id>")
@login_required
def venda_detalhe(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    cliente = Cliente.query.get(venda.cliente_id) if venda.cliente_id else None
    itens = ItemVenda.query.filter_by(venda_id=venda.id).all()

    return render_template(
        "vendas/detalhe.html",
        venda=venda,
        cliente=cliente,
        itens=itens
    )

@vendas_bp.route("/<int:venda_id>/editar", methods=["GET", "POST"])
@login_required
def editar_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    cliente = Cliente.query.get(venda.cliente_id) if venda.cliente_id else None
    itens = ItemVenda.query.filter_by(venda_id=venda.id).all() # Carrega os itens

    if request.method == "POST":
        # Lógica futura para editar itens
        pass

    # Lógica GET para popular o formulário 
    itens_data = []
    for i in itens:
        detalhe_html = '<span class="text-muted small">Item de Varejo</span>'
        
        # Para itens de estoque rastreados
        if i.item_estoque:
            # Lógica para gerar o detalhe_html com base no ItemEstoque (Serial/Lote)
            if i.item_estoque.numero_serie:
                detalhe_html = f'<span class="badge bg-dark"><i class="fas fa-fingerprint"></i> Serial: {i.item_estoque.numero_serie}</span>'
            elif i.item_estoque.lote or i.item_estoque.numero_embalagem:
                detalhe_html = f'<span class="badge bg-info text-dark"><i class="fas fa-box"></i> Lote: {i.item_estoque.lote or i.item_estoque.numero_embalagem}</span>'

        # Para munição vinculada a CRAF
        if i.arma_cliente:
            craf_texto = f"{i.arma_cliente.tipo} {i.arma_cliente.calibre} ({i.arma_cliente.numero_serie or 'S/N'})"
            detalhe_html += f'<div class="mt-1 small text-primary"><i class="fas fa-id-card"></i> Ref: {craf_texto}</div>'

        # Para armas sob encomenda (Heurística: Produto tipo arma sem item_estoque_id)
        if not i.item_estoque_id and i.produto and 'arma' in (i.produto.tipo_rel.nome if i.produto.tipo_rel else '').lower():
            detalhe_html = '<span class="badge bg-warning text-dark">Sob Encomenda</span>'
        
        itens_data.append({
            'produto_id': i.produto_id,
            'nome': i.produto_nome,
            'preco': float(i.valor_unitario),
            'quantidade': i.quantidade,
            'item_estoque_id': i.item_estoque_id,
            'arma_cliente_id': i.arma_cliente_id,
            'detalhe_html': detalhe_html # Usado no frontend para exibir na tabela
        })

    venda_data = {
        'id': venda.id,
        'cliente': {
            'id': cliente.id, 
            # CORREÇÃO DO BUG: Usar getattr com fallback para evitar AttributeError
            'nome': getattr(cliente, 'razao_social', cliente.nome) or cliente.nome,
            'documento': cliente.documento, 
            'cr': cliente.cr
        } if cliente else None,
        'desconto': float(venda.desconto_valor) if venda.desconto_valor else 0.0,
        'itens': itens_data
    }
    
    return render_template(
        "vendas/form.html",
        venda=venda,
        edicao=True,
        venda_json=venda_data # Passa os dados serializados para o JS
    )


@vendas_bp.route("/<int:venda_id>/excluir", methods=["POST"])
@login_required
def excluir_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    try:
        db.session.delete(venda)
        db.session.commit()
        flash(f"Venda #{venda_id} excluída com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir venda: {str(e)}", "danger")
        
    return redirect(url_for("vendas.vendas"))


@vendas_bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova_venda():
    """Rota principal de Nova Venda. REDIRECIONA para o Novo PDV (Ação 12)."""
    flash("Você foi redirecionado para a Nova Tela de Vendas (PDV).", "info")
    # Redirecionamento 301 (Permanente) para a rota no novo Blueprint
    return redirect(url_for("sales_core.novo_pdv"), code=301)


# ===============================================================
# APIs INTERNAS (JSON) - Antigas (Devem ser descontinuadas ou migradas)
# ===============================================================

@vendas_bp.route("/api/clientes")
@login_required
def api_buscar_clientes():
    termo = request.args.get("q", "")
    clientes = Cliente.query.filter(
        (Cliente.nome.ilike(f"%{termo}%")) | 
        (Cliente.documento.ilike(f"%{termo}%"))
    ).limit(10).all()
    
    # CORREÇÃO DO BUG: Usar getattr com fallback para evitar AttributeError
    return jsonify([{
        "id": c.id, 
        "nome": getattr(c, 'razao_social', c.nome) or c.nome, # Prefere nome mais completo
        "documento": c.documento,
        "cr": c.cr
    } for c in clientes])


# --- Lógica de Calibre ---
def normalizar_calibre(texto):
    if not texto:
        return ""
    limpo = texto.lower().replace(".", "").replace("-", "").replace(" ", "")
    termos_para_remover = [
        "acp", "auto", "spl", "special", "win", "rem", "magnum", 
        "parabellum", "luger", "mm", "ga", "gauge", "long", "lr", "short"
    ]
    for termo in termos_para_remover:
        limpo = limpo.replace(termo, "")
    return limpo


@vendas_bp.route("/api/cliente/<int:cliente_id>/armas")
@login_required
def api_armas_cliente(cliente_id):
    calibre_alvo = request.args.get("calibre")
    todas_armas = Arma.query.filter_by(cliente_id=cliente_id).all()
    
    armas_filtradas = []
    
    if calibre_alvo:
        alvo_limpo = normalizar_calibre(calibre_alvo)
        
        # Tabela de equivalência para aumentar a chance de match
        equivalencias = {
            "9": ["9x19", "9", "380"],
            "9x19": ["9", "9x19"],
            "38": ["38", "357"],
            "357": ["357"],
            "380": ["380"],
            "12": ["12"],
            "22": ["22"],
            "40": ["40", "40sw"],
            "45": ["45", "45acp"]
        }
        compativeis = equivalencias.get(alvo_limpo, [alvo_limpo])

        for arma in todas_armas:
            arma_calibre_limpo = normalizar_calibre(arma.calibre)
            match = False
            if alvo_limpo == "38" and "357" in arma_calibre_limpo:
                match = True
            else:
                for c in compativeis:
                    if c == arma_calibre_limpo or c in arma_calibre_limpo or arma_calibre_limpo in c:
                        match = True
                        break
            
            if match:
                armas_filtradas.append(arma)
    else:
        armas_filtradas = todas_armas

    return jsonify([{
        "id": a.id,
        "descricao": f"{a.tipo or 'Arma'} {a.marca or ''} {a.modelo or ''}",
        "descricao_curta": f"{a.tipo} {a.calibre}", 
        "serial": a.numero_serie,
        "calibre": a.calibre,
        "caminho_craf": a.caminho_craf,
        "sistema": f"{a.emissor_craf or a.numero_sigma or 'S/N'}" 
    } for a in armas_filtradas])


@vendas_bp.route("/api/produto/<int:produto_id>/detalhes")
@login_required
def api_produto_detalhes(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    
    # Busca as embalagens cadastradas (se existirem no futuro)
    embalagens = []
    # for emb in produto.embalagens: ... (implementação futura)
    
    # Adicionar quantidade padrão de venda 
    unidade_venda_padrao = getattr(produto, 'unidade_venda_padrao', 1) 

    return jsonify({
        "id": produto.id,
        "nome": produto.nome,
        "preco": float(produto.preco_a_vista or 0),
        # "estoque": sum(i.quantidade for i in produto.itens_estoque if i.status == 'disponivel'), # Ajuste conforme sua lógica
        "estoque": 10, # Placeholder
        "tipo": (produto.tipo_rel.nome if produto.tipo_rel else "").lower(),
        "categoria": (produto.categoria.nome if produto.categoria else "").lower(),
        "calibre": (produto.calibre_rel.nome if produto.calibre_rel else ""),
        "embalagens": embalagens,
        "unidade_venda_padrao": unidade_venda_padrao # NOVO CAMPO
    })


@vendas_bp.route("/api/produtos")
@login_required
def api_buscar_produtos():
    termo = request.args.get("q", "")
    produtos = Produto.query.filter(
        (Produto.nome.ilike(f"%{termo}%")) | 
        (Produto.codigo.ilike(f"%{termo}%"))
    ).limit(10).all()
    
    return jsonify([{
        "id": p.id,
        "nome": p.nome,
        "preco": float(p.preco_a_vista or 0),
        "estoque": 10 
    } for p in produtos])


@vendas_bp.route("/api/estoque/<int:produto_id>")
@login_required
def api_buscar_estoque_produto(produto_id):
    itens = ItemEstoque.query.filter_by(
        produto_id=produto_id, 
        status="disponivel"
    ).all()
    
    return jsonify([{
        "id": i.id,
        "serial": i.numero_serie,
        "lote": i.lote,
        "embalagem": i.numero_embalagem 
    } for i in itens])

# ===============================================================
# GERAÇÃO DE DOCUMENTOS E UPLOADS
# ===============================================================

@vendas_bp.route("/<int:venda_id>/documento/<chave>")
@login_required
def gerar_documento(venda_id, chave):
    venda = Venda.query.get_or_404(venda_id)
    modelo = ModeloDocumento.query.filter_by(chave=chave).first_or_404()
    
    # Dados da Empresa
    empresa = {
        "razao_social": "M4 TÁTICA COMERCIO E SERVIÇOS LTDA",
        "cnpj": "41.654.218/0001-47",
        "endereco": "AV. UNIVERSITÁRIA, 750 - LJ 23, FÁTIMA, TERESINA/PI",
        "cr": "635069",
        "telefone": "(86) 3025-5885",
        "email": "falecom@m4tatica.com.br",
        # ALTERADO PARA USAR A LOGO ESPECÍFICA 'logo_docs.png'
        "logo": url_for('static', filename='img/logo_docs.png', _external=True) 
    }

    c = venda.cliente
    end = c.enderecos[0] if c.enderecos else None
    end_str = f"{end.logradouro}, {end.numero}, {end.bairro} - {end.cidade}/{end.estado} - CEP {end.cep}" if end else "Endereço não cadastrado"
    tel = c.contatos[0].valor if c.contatos else "Não informado"

    context = {
        "venda": venda,
        "br_money": br_money,
        "cliente": {
            "nome": c.nome,
            "documento": c.documento or "",
            "rg": c.rg or "",
            "rg_emissor": c.rg_emissor or "",
            "endereco_completo": end_str,
            "email": "", 
            "telefone": tel,
            "cr": c.cr or "",
            "cr_validade": c.data_validade_cr.strftime('%d/%m/%Y') if c.data_validade_cr else ""
        },
        "empresa": empresa,
        "data_hoje": datetime.today().strftime('%d/%m/%Y'),
        "itens_lista": "<br>".join([f"- {i.produto_nome} (Qtd: {i.quantidade})" for i in venda.itens])
    }
    
    conteudo_renderizado = render_template_string(modelo.conteudo, **context)
    
    return render_template("vendas/print_documento.html", conteudo=conteudo_renderizado, titulo=modelo.titulo)


@vendas_bp.route("/<int:venda_id>/upload", methods=["POST"])
@login_required
def upload_anexo(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    
    if "arquivo" not in request.files:
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for("vendas.venda_detalhe", venda_id=venda_id))
        
    arquivo = request.files["arquivo"]
    tipo_doc = request.form.get("tipo_documento", "outros")
    
    if arquivo.filename == "":
        flash("Nome do arquivo inválido.", "warning")
        return redirect(url_for("vendas.venda_detalhe", venda_id=venda_id))

    try:
        # Enviar para o Cloudflare R2
        url_publica = upload_file_to_r2(arquivo, folder=f"vendas/{venda_id}")
        
        if not url_publica:
            raise Exception("Falha no upload para o storage.")

        # Salvar no Banco
        novo_anexo = VendaAnexo(
            venda_id=venda.id,
            tipo_documento=tipo_doc,
            nome_arquivo=arquivo.filename,
            url_arquivo=url_publica,
            enviado_por=current_user.username
        )
        
        db.session.add(novo_anexo)
        
        # Se for termo de retirada, avança status
        if tipo_doc == 'termo_assinado':
            venda.etapa = "CONCLUIDA"
            venda.status = "fechada"
            venda.data_entrega_efetiva = datetime.now()
            venda.data_fechamento = datetime.now()
            flash("Termo anexado e venda CONCLUÍDA com sucesso!", "success")
        else:
            flash("Documento anexado com sucesso.", "success")
            
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro upload anexo venda {venda_id}: {e}")
        flash(f"Erro ao salvar arquivo: {str(e)}", "danger")

    return redirect(url_for("vendas.venda_detalhe", venda_id=venda_id))