# ===========================================================
# ROTAS — AUTOSAVE DE PRODUTOS
# Módulo revisado — Correção Crítica de Tipos (Sprint 6I)
# ===========================================================

from flask import request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from app import db
from app.produtos.models import Produto, ProdutoFoto, ProdutoVideo
from app.produtos.utils.historico_helper import registrar_historico
from app.utils.parsing import parse_decimal, parse_form_datetime
from app.utils.datetime import now_local

# Importamos o Blueprint principal do módulo
from .. import produtos_bp 

# Lista de campos que DEVEM passar pela conversão numérica
CAMPOS_DECIMAIS = [
    "preco_fornecedor", "desconto_fornecedor", "frete", "margem", 
    "ipi", "difal", "imposto_venda", "lucro_alvo", "preco_final", 
    "promo_preco_fornecedor", "custo_total", "preco_a_vista", "lucro_liquido_real"
]

# Lista de campos que são datas (para parser futuro se necessário)
CAMPOS_DATAS = ["promo_data_inicio", "promo_data_fim"]

# ===========================================================
# Função utilitária para converter valores corretamente (CORRIGIDA)
# ===========================================================
def _parse_decimal(valor):
    """
    Converte string numérica para Decimal, removendo símbolos e tratando
    o formato brasileiro (ponto como milhar, vírgula como decimal).
    Ex: "R$ 9.750,50" -> Decimal('9750.50')
    """
    return parse_decimal(valor)

@produtos_bp.route("/autosave/<int:produto_id>", methods=["POST"])
@login_required
def autosave_produto(produto_id):
    import json
    produto = Produto.query.get_or_404(produto_id)
    data = request.get_json() or {}
    alteracoes = {}

    # A galeria é enviada como JSON pelo formulário. Como fotos não são
    # colunas diretas de Produto, precisam ser sincronizadas explicitamente
    # aqui; antes, o autosave descartava a alteração ao trocar de aba.
    fotos_payload = data.get("fotos_produto")
    if fotos_payload is not None:
        try:
            fotos_recebidas = json.loads(fotos_payload) if isinstance(fotos_payload, str) else fotos_payload
            if not isinstance(fotos_recebidas, list):
                fotos_recebidas = None
        except (TypeError, ValueError):
            fotos_recebidas = None

        if fotos_recebidas is not None:
            fotos_recebidas = [
                item for item in fotos_recebidas
                if isinstance(item, dict) and str(item.get("url") or "").strip()
            ]
            principal = next((item for item in fotos_recebidas if item.get("principal")), None)
            principal_url = (principal or (fotos_recebidas[0] if fotos_recebidas else {})).get("url")
            fotos_atuais = ProdutoFoto.query.filter_by(produto_id=produto.id).order_by(
                ProdutoFoto.ordem.asc(), ProdutoFoto.id.asc()
            ).all()
            estado_atual = [
                {"url": foto.url, "principal": bool(foto.eh_principal)}
                for foto in fotos_atuais
            ]
            estado_novo = [
                {"url": item["url"], "principal": item["url"] == principal_url}
                for item in fotos_recebidas
            ]
            if estado_atual != estado_novo or produto.foto_url != principal_url:
                produto.fotos.clear()
                for ordem, item in enumerate(estado_novo):
                    produto.fotos.append(ProdutoFoto(
                        url=item["url"],
                        eh_principal=item["principal"],
                        ordem=ordem,
                    ))
                alteracoes["fotos_produto"] = {
                    "antigo": estado_atual,
                    "novo": estado_novo,
                }
                produto.foto_url = principal_url or None

    videos_payload = data.get("videos_produto")
    if videos_payload is not None:
        try:
            videos_recebidos = json.loads(videos_payload) if isinstance(videos_payload, str) else videos_payload
            if not isinstance(videos_recebidos, list):
                videos_recebidos = None
        except (TypeError, ValueError):
            videos_recebidos = None
        if videos_recebidos is not None:
            videos_novos = [
                {"url": str(item.get("url") or "").strip(), "titulo": str(item.get("titulo") or "").strip()[:180]}
                for item in videos_recebidos
                if isinstance(item, dict) and str(item.get("url") or "").strip()
            ]
            videos_atuais = ProdutoVideo.query.filter_by(produto_id=produto.id).order_by(
                ProdutoVideo.ordem.asc(), ProdutoVideo.id.asc()
            ).all()
            estado_atual_videos = [{"url": video.url, "titulo": video.titulo or ""} for video in videos_atuais]
            if estado_atual_videos != videos_novos:
                produto.videos.clear()
                for ordem, item in enumerate(videos_novos):
                    produto.videos.append(ProdutoVideo(url=item["url"], titulo=item["titulo"] or None, ordem=ordem))
                alteracoes["videos_produto"] = {"antigo": estado_atual_videos, "novo": videos_novos}

    CAMPOS_BOOLEANOS = ["promo_ativada", "visivel_loja", "destaque_home", "eh_lancamento", "eh_outdoor", "requer_documentacao"]

    for campo, valor_novo in data.items():
        if not hasattr(produto, campo):
            continue

        valor_atual = getattr(produto, campo)
        valor_final = valor_novo

        if campo == "especificacoes_tecnicas":
            try:
                # Converte string em dicionário se necessário
                valor_final = json.loads(valor_novo) if isinstance(valor_novo, str) else valor_novo
            except:
                valor_final = {}
        elif campo in CAMPOS_DECIMAIS:
            valor_final = _parse_decimal(valor_novo)
        elif campo in CAMPOS_BOOLEANOS:
            valor_final = str(valor_novo).lower() in ['true', 'on', '1']
        elif campo == "meta_description":
            valor_final = str(valor_novo)[:160] if valor_novo else None
        elif campo == "nome_comercial":
            produto.meta_title = valor_novo
            valor_final = valor_novo
        elif campo in CAMPOS_DATAS:
            valor_final = parse_form_datetime(valor_novo)
        else:
            if isinstance(valor_novo, str):
                valor_final = valor_novo.strip()
                if valor_final == "": valor_final = None

        if campo in ["nome", "codigo"] and not valor_final:
            continue

        if str(valor_atual) != str(valor_final):
            alteracoes[campo] = {"antigo": valor_atual, "novo": valor_final}
            setattr(produto, campo, valor_final)

    if not alteracoes:
        return jsonify({"status": "no_changes"}), 200

    if hasattr(produto, 'calcular_precos'):
        produto.calcular_precos()

    produto.atualizado_em = now_local()
    registrar_historico(produto, current_user, "autosave", alteracoes)

    try:
        db.session.commit()
        return jsonify({"status": "success", "atualizado_em": produto.atualizado_em.strftime('%H:%M')}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# ===========================================================
# ROTA — Autosave em lote (Mantido estrutura, aplicado fix)
# ===========================================================
@produtos_bp.route("/autosave/lote", methods=["POST"])
@login_required
def autosave_lote():
    payload = request.get_json() or {}
    produtos_data = payload.get("produtos", [])
    resultados = []

    for item in produtos_data:
        produto_id = item.get("id")
        produto = Produto.query.get(produto_id)
        if not produto:
            continue

        alteracoes = {}
        for campo, valor_novo in item.items():
            if campo == "id" or not hasattr(produto, campo):
                continue

            # Aplica mesma lógica segura
            if campo in CAMPOS_DECIMAIS:
                valor_final = _parse_decimal(valor_novo)
            elif campo == "promo_ativada":
                valor_final = str(valor_novo).lower() in ['true', 'on', '1']
            elif campo in CAMPOS_DATAS:
                valor_final = parse_form_datetime(valor_novo)
            else:
                valor_final = valor_novo
                if isinstance(valor_final, str):
                    valor_final = valor_final.strip() or None

            # Proteção
            if campo in ["nome", "codigo"] and not valor_final:
                continue

            valor_atual = getattr(produto, campo)
            if str(valor_atual) != str(valor_final):
                alteracoes[campo] = {"antigo": valor_atual, "novo": valor_final}
                setattr(produto, campo, valor_final)

        if alteracoes:
            if hasattr(produto, 'calcular_precos'):
                produto.calcular_precos()
            produto.atualizado_em = now_local()
            registrar_historico(produto, current_user, "autosave", alteracoes)
            resultados.append(produto.id)

    db.session.commit()
    return jsonify({"status": "success", "ids": resultados}), 200

@produtos_bp.route("/autosave/ping", methods=["GET"])
@login_required
def autosave_ping():
    return jsonify({"status": "ok"}), 200
