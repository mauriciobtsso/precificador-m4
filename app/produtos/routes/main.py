from flask import render_template, request, redirect, url_for, flash, current_app, make_response
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import pytz
import time
import json

from app import db
from .. import produtos_bp
from app.produtos.models import Produto, ProdutoFoto, ProdutoVideo, ProdutoTour360, ProdutoHistorico
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto, CalibreProduto, TipoProduto, FuncionamentoProduto
)

from app.models import Taxa
import app.utils.parcelamento as parc
from app.utils.datetime import now_local
from app.utils.parsing import parse_decimal, parse_form_datetime

from urllib.parse import urlparse
from app.produtos.routes.utils import _key_from_url

from app.utils.r2_helpers import gerar_link_r2

# ============================================================
#  Cache leve em memória para fragmentos da listagem (AJAX)
# ============================================================
_LIST_CACHE = {}  
_LIST_CACHE_TTL = 60 

def _cache_key_for_list(page: int, per_page: int, ordenar: str) -> str:
    return f"nofilter:p={page}:pp={per_page}:ord={ordenar}"

def _get_cached_fragment(page: int, per_page: int, ordenar: str):
    key = _cache_key_for_list(page, per_page, ordenar)
    item = _LIST_CACHE.get(key)
    now = time.time()
    if item and item[0] > now:
        return item[1]
    if item:
        _LIST_CACHE.pop(key, None)
    return None

def _set_cached_fragment(page: int, per_page: int, ordenar: str, html: str):
    key = _cache_key_for_list(page, per_page, ordenar)
    _LIST_CACHE[key] = (time.time() + _LIST_CACHE_TTL, html)

@produtos_bp.app_context_processor
def utility_processor():
    def gerar_link(path):
        if not path:
            return ""
        # Se já for uma URL completa, retorna ela mesma
        if path.startswith('http'):
            return path
        # Caso contrário, usa o helper do R2 para montar o link assinado ou público
        return gerar_link_r2(path)
    
    return dict(gerar_link=gerar_link)


# ============================================================
# LISTAGEM DE PRODUTOS
# ============================================================
@produtos_bp.route("/", endpoint="index")
@login_required
def index():
    raw_termo = (request.args.get("termo") or "").strip()
    termo = raw_termo if raw_termo else ""

    def _to_int(qs_name):
        try:
            v = request.args.get(qs_name, type=int)
            return v if v and v > 0 else None
        except Exception:
            return None

    tipo = _to_int("tipo")
    categoria = _to_int("categoria")
    marca = _to_int("marca")
    calibre = _to_int("calibre")

    ordenar = request.args.get("ordenar", "nome_asc")
    ordem_map = {
        "nome_asc": Produto.nome.asc(),
        "nome_desc": Produto.nome.desc(),
        "preco_asc": Produto.preco_a_vista.asc(),
        "preco_desc": Produto.preco_a_vista.desc(),
        "lucro_asc": Produto.lucro_liquido_real.asc(),
        "lucro_desc": Produto.lucro_liquido_real.desc(),
        "atualizado_em_desc": Produto.atualizado_em.desc(),
    }
    ordem = ordem_map.get(ordenar, Produto.nome.asc())

    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", 20, type=int) or 20
    if per_page < 10: per_page = 10
    if per_page > 100: per_page = 100

    query = Produto.query
    if termo:
        like = f"%{termo}%"
        query = query.filter(or_(Produto.nome.ilike(like), Produto.codigo.ilike(like)))

    if tipo: query = query.filter(Produto.tipo_id == tipo)
    if categoria: query = query.filter(Produto.categoria_id == categoria)
    if marca: query = query.filter(Produto.marca_id == marca)
    if calibre: query = query.filter(Produto.calibre_id == calibre)

    query = query.order_by(ordem)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    produtos = pagination.items

    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()

    wants_fragment = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    has_any_filter = any([bool(termo), bool(tipo), bool(categoria), bool(marca), bool(calibre)])

    agora = now_local()
    precos_atuais = {produto.id: produto.calcular_precos() for produto in produtos}

    if wants_fragment:
        # Preços de promoção dependem do instante atual; não reutilizar HTML
        # armazenado para evitar exibir uma promoção depois do seu término.
        html = render_template(
            "produtos/_lista.html", produtos=produtos, pagination=pagination,
            per_page=per_page, request=request, agora=agora,
            precos_atuais=precos_atuais,
        )
        resp = make_response(html)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return render_template(
        "produtos/index.html", produtos=produtos, pagination=pagination,
        tipos=tipos, categorias=categorias, marcas=marcas, calibres=calibres,
        per_page=per_page, agora=agora, precos_atuais=precos_atuais,
    )


# ============================================================
# CADASTRAR / EDITAR PRODUTO (VERSÃO FINAL BLINDADA)
# ============================================================
@produtos_bp.route("/novo", methods=["GET", "POST"])
@produtos_bp.route("/<int:produto_id>/editar", methods=["GET", "POST"])
@login_required
def gerenciar_produto(produto_id=None):
    import json # Import necessário para tratar o JSON
    duplicar_de = request.args.get("duplicar_de", type=int)

    if duplicar_de:
        produto_ref = Produto.query.get(duplicar_de)
        if produto_ref:
            produto = Produto(
                nome=produto_ref.nome,
                nome_comercial=produto_ref.nome_comercial,
                descricao=produto_ref.descricao,
                descricao_comercial=produto_ref.descricao_comercial,
                descricao_longa=produto_ref.descricao_longa,
                categoria_id=produto_ref.categoria_id,
                tipo_id=produto_ref.tipo_id,
                marca_id=produto_ref.marca_id,
                calibre_id=produto_ref.calibre_id,
                funcionamento_id=produto_ref.funcionamento_id,
                preco_fornecedor=produto_ref.preco_fornecedor,
                desconto_fornecedor=produto_ref.desconto_fornecedor,
                frete=produto_ref.frete,
                margem=produto_ref.margem,
                lucro_alvo=produto_ref.lucro_alvo,
                preco_final=produto_ref.preco_final,
                ipi_tipo=produto_ref.ipi_tipo,
                ipi=produto_ref.ipi,
                difal=produto_ref.difal,
                imposto_venda=produto_ref.imposto_venda,
                requer_documentacao=produto_ref.requer_documentacao,
                visivel_loja=False 
            )
            flash(f"Produto '{produto_ref.nome}' duplicado. Revise antes de salvar.", "info")
        else:
            flash("⚠️ Produto de origem não encontrado.", "warning")
            produto = Produto()
    else:
        if produto_id:
            produto = Produto.query.options(joinedload(Produto.historicos)).filter_by(id=produto_id).first()
        else:
            produto = Produto()

    categorias = CategoriaProduto.query.order_by(CategoriaProduto.nome.asc()).all()
    marcas = MarcaProduto.query.order_by(MarcaProduto.nome.asc()).all()
    calibres = CalibreProduto.query.order_by(CalibreProduto.nome.asc()).all()
    tipos = TipoProduto.query.order_by(TipoProduto.nome.asc()).all()
    funcionamentos = FuncionamentoProduto.query.order_by(FuncionamentoProduto.nome.asc()).all()
    produtos_para_acessorios = Produto.query.filter(Produto.id != (produto.id or -1)).order_by(Produto.nome.asc()).all()

    if request.method == "POST":
        data = request.form
        foto_atual = getattr(produto, "foto_url", None)

        def to_int(value):
            try: return int(value) if value else None
            except ValueError: return None

        def to_decimal(value):
            return parse_decimal(value) or Decimal(0)

        campos_auditados = [
            "codigo", "nome", "nome_comercial", "slug", "descricao", "descricao_comercial", "descricao_longa",
            "categoria_id", "marca_id", "calibre_id", "tipo_id", "funcionamento_id",
            "preco_fornecedor", "desconto_fornecedor", "frete", "margem", "lucro_alvo", "preco_final",
            "ipi", "ipi_tipo", "difal", "imposto_venda", "meta_title", "meta_description",
            "visivel_loja", "requer_documentacao", "destaque_home", "eh_lancamento", "eh_outdoor",
            "promo_ativada", "promo_preco_fornecedor", "promo_data_inicio", "promo_data_fim"
        ]
        antes = {c: getattr(produto, c, None) for c in campos_auditados}

        # --- SALVAMENTO COM VALIDAÇÕES DETALHADAS ---
        try:
            # Validação: Código é obrigatório
            codigo = (data.get("codigo") or "").strip().upper()
            if not codigo:
                flash("❌ Erro: O código do produto é obrigatório.", "danger")
                return render_template(
                    "produtos/form/produto_form.html",
                    produto=produto,
                    categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos, produtos_para_acessorios=produtos_para_acessorios,
                )
            produto.codigo = codigo

            # Validação: Nome é obrigatório
            nome = (data.get("nome") or "").strip()
            if not nome:
                flash("❌ Erro: O nome do produto é obrigatório.", "danger")
                return render_template(
                    "produtos/form/produto_form.html",
                    produto=produto,
                    categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos, produtos_para_acessorios=produtos_para_acessorios,
                )
            produto.nome = nome

            produto.nome_comercial = (data.get("nome_comercial") or "").strip() or None
            meta_title_raw = (data.get("meta_title") or "").strip()
            produto.meta_title = meta_title_raw[:120] if meta_title_raw else None

            if data.get("slug"):
                produto.slug = data.get("slug").strip().lower()

            produto.descricao = (data.get("descricao") or "").strip() or None
            produto.descricao_longa = request.form.get("descricao_longa", "")
            produto.descricao_comercial = (data.get("descricao_comercial") or "").strip() or None
            
            desc_google = (data.get("meta_description") or "").strip()
            meta_desc_raw = (data.get("meta_description") or "").strip()
            produto.meta_description = meta_desc_raw[:250] if meta_desc_raw else None

            # Validação: Categoria é obrigatória
            categoria_id = to_int(data.get("categoria_id"))
            if not categoria_id:
                flash("❌ Erro: A categoria do produto é obrigatória.", "danger")
                return render_template(
                    "produtos/form/produto_form.html",
                    produto=produto,
                    categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos, produtos_para_acessorios=produtos_para_acessorios,
                )
            produto.categoria_id = categoria_id

            produto.marca_id = to_int(data.get("marca_id"))
            produto.calibre_id = to_int(data.get("calibre_id"))
            
            # Validação: Tipo é obrigatório
            tipo_id = to_int(data.get("tipo_id"))
            if not tipo_id:
                flash("❌ Erro: O tipo do produto é obrigatório.", "danger")
                return render_template(
                    "produtos/form/produto_form.html",
                    produto=produto,
                    categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos, produtos_para_acessorios=produtos_para_acessorios,
                )
            produto.tipo_id = tipo_id

            produto.funcionamento_id = to_int(data.get("funcionamento_id"))

            # Validação: Preço do fornecedor deve ser positivo
            preco_fornecedor = to_decimal(data.get("preco_fornecedor"))
            if preco_fornecedor <= 0:
                flash("❌ Erro: O preço do fornecedor deve ser maior que zero.", "danger")
                return render_template(
                    "produtos/form/produto_form.html",
                    produto=produto,
                    categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos, produtos_para_acessorios=produtos_para_acessorios,
                )
            produto.preco_fornecedor = preco_fornecedor

            produto.desconto_fornecedor = to_decimal(data.get("desconto_fornecedor"))
            produto.frete = to_decimal(data.get("frete"))
            produto.margem = to_decimal(data.get("margem"))
            produto.lucro_alvo = to_decimal(data.get("lucro_alvo"))
            produto.preco_final = to_decimal(data.get("preco_final"))
            produto.ipi = to_decimal(data.get("ipi"))
            produto.difal = to_decimal(data.get("difal"))
            produto.imposto_venda = to_decimal(data.get("imposto_venda"))
            produto.ipi_tipo = data.get("ipi_tipo", "%_dentro")

            produto.visivel_loja = data.get("visivel_loja") == "on"
            produto.requer_documentacao = data.get("requer_documentacao") == "on"
            produto.destaque_home = data.get("destaque_home") == "on"
            produto.eh_lancamento = data.get("eh_lancamento") == "on"
            produto.eh_outdoor = data.get("eh_outdoor") == "on"

            produto.promo_ativada = data.get("promo_ativada") == "on"
            produto.promo_preco_fornecedor = to_decimal(data.get("promo_preco_fornecedor"))
            produto.promo_data_inicio = parse_form_datetime(data.get("promo_data_inicio"))
            produto.promo_data_fim = parse_form_datetime(data.get("promo_data_fim"))

            fotos_payload = data.get("fotos_produto")
            try:
                fotos_enviadas = json.loads(fotos_payload) if fotos_payload else None
                if not isinstance(fotos_enviadas, list):
                    fotos_enviadas = None
            except (TypeError, ValueError):
                fotos_enviadas = None
            # Mantém compatibilidade com formulários/integradores antigos.
            if fotos_enviadas is None:
                produto.foto_url = data.get("foto_url") or foto_atual
            else:
                fotos_enviadas = [item for item in fotos_enviadas if isinstance(item, dict) and item.get("url")]
                principal = next((item for item in fotos_enviadas if item.get("principal")), None)
                produto.foto_url = (principal or (fotos_enviadas[0] if fotos_enviadas else {})).get("url") or None

            videos_payload = data.get("videos_produto")
            try:
                videos_enviados = json.loads(videos_payload) if videos_payload else None
                if not isinstance(videos_enviados, list):
                    videos_enviados = None
            except (TypeError, ValueError):
                videos_enviados = None
            if videos_enviados is not None:
                videos_enviados = [
                    {"url": str(item.get("url")).strip(), "titulo": str(item.get("titulo") or "").strip()[:180]}
                    for item in videos_enviados
                    if isinstance(item, dict) and str(item.get("url") or "").strip()
                ]

            tour360_payload = data.get("tour360_produto")
            try:
                tour360_enviado = json.loads(tour360_payload) if tour360_payload else None
                if not isinstance(tour360_enviado, dict):
                    tour360_enviado = None
            except (TypeError, ValueError):
                tour360_enviado = None
            if tour360_enviado is not None:
                frames = tour360_enviado.get("frames") or []
                tour360_enviado = {
                    "titulo": str(tour360_enviado.get("titulo") or "").strip()[:180],
                    "ativo": bool(tour360_enviado.get("ativo", True)),
                    "frames": [
                        str(frame.get("url") or "").strip()
                        for frame in frames
                        if isinstance(frame, dict) and str(frame.get("url") or "").strip()
                    ],
                }

            acessorios_payload = data.get("acessorios_produto")
            try:
                acessorios_ids = json.loads(acessorios_payload) if acessorios_payload else None
                if not isinstance(acessorios_ids, list):
                    acessorios_ids = None
            except (TypeError, ValueError):
                acessorios_ids = None
            if acessorios_ids is not None:
                acessorios_ids = list(dict.fromkeys(
                    int(item) for item in acessorios_ids if str(item).isdigit() and int(item) != produto.id
                ))

            # No trecho onde você coleta os dados do request:
            produto.peso = to_decimal(data.get('peso'))
            produto.comprimento = to_decimal(data.get('comprimento'))
            produto.largura = to_decimal(data.get('largura'))
            produto.altura = to_decimal(data.get('altura'))

            # --- TRATAMENTO ESPECIFICAÇÕES TÉCNICAS (BLINDAGEM) ---
            specs_json = data.get("especificacoes_tecnicas")
            if specs_json:
                try:
                    produto.especificacoes_tecnicas = json.loads(specs_json)
                except (ValueError, TypeError) as e:
                    flash(f"⚠️ Aviso: Especificações técnicas inválidas (JSON malformado). Foram ignoradas.", "warning")
                    produto.especificacoes_tecnicas = {}

            # --- CÁLCULO E SALVAMENTO ---
            if hasattr(produto, "calcular_precos"):
                produto.calcular_precos()

            db.session.add(produto)
            db.session.flush()

 
            # ============================================================
            # MIGRAR FOTO DO TEMP PARA A PASTA DEFINITIVA DO PRODUTO NO R2
            # ============================================================
            if fotos_enviadas is None and produto.foto_url and 'produtos/fotos/temp/' in produto.foto_url:
                try:
                    from app.produtos.routes.utils import _r2_client, _r2_bucket_publico
                    client = _r2_client()
                    bucket = _r2_bucket_publico()
 
                    # ✅ _key_from_url agora remove o prefixo do bucket do path
                    old_key = _key_from_url(produto.foto_url)
 
                    if old_key and 'produtos/fotos/temp/' in old_key:
                        new_key = old_key.replace(
                            'produtos/fotos/temp/',
                            f'produtos/fotos/{produto.id}/'
                        )
 
                        # Copia a foto principal
                        client.copy_object(
                            Bucket=bucket,
                            CopySource={'Bucket': bucket, 'Key': old_key},
                            Key=new_key
                        )
                        client.delete_object(Bucket=bucket, Key=old_key)
 
                        # ✅ Reconstrói a URL usando o CDN, não a URL antiga com bug
                        from app.utils.r2_helpers import CDN_URL
                        produto.foto_url = f"{CDN_URL}/{new_key}"
 
                        # Tenta mover thumbnails (t280, t160) se já existirem
                        for size in ['t280', 't160']:
                            from pathlib import Path as _Path
                            old_p = _Path(old_key)
                            new_p = _Path(new_key)
                            old_thumb = str(old_p.parent / f"{old_p.stem}_{size}.webp")
                            new_thumb = str(new_p.parent / f"{new_p.stem}_{size}.webp")
                            try:
                                client.copy_object(
                                    Bucket=bucket,
                                    CopySource={'Bucket': bucket, 'Key': old_thumb},
                                    Key=new_thumb
                                )
                                client.delete_object(Bucket=bucket, Key=old_thumb)
                            except Exception:
                                pass  # Thumbnail ainda não gerado, será criado pelo hook
 
                        current_app.logger.info(
                            f"[M4] Foto migrada: temp → produtos/fotos/{produto.id}/ | "
                            f"nova URL: {produto.foto_url}"
                        )
                except Exception as e:
                    current_app.logger.error(
                        f"[M4] Erro ao migrar foto temp para definitivo (produto {produto.id}): {e}"
                    )

            # ============================================================
            # SINCRONIZAR GALERIA DE FOTOS E IMAGEM PRINCIPAL
            # ============================================================
            if fotos_enviadas is not None:
                for item in fotos_enviadas:
                    foto_url = item["url"]
                    if "produtos/fotos/temp/" not in foto_url:
                        continue
                    try:
                        from app.produtos.routes.utils import _r2_client, _r2_bucket_publico
                        from app.utils.r2_helpers import CDN_URL
                        client = _r2_client()
                        bucket = _r2_bucket_publico()
                        old_key = _key_from_url(foto_url)
                        if old_key and "produtos/fotos/temp/" in old_key:
                            new_key = old_key.replace("produtos/fotos/temp/", f"produtos/fotos/{produto.id}/")
                            client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": old_key}, Key=new_key)
                            client.delete_object(Bucket=bucket, Key=old_key)
                            item["url"] = f"{CDN_URL}/{new_key}"
                    except Exception as e:
                        current_app.logger.error("Erro ao migrar foto da galeria do produto %s: %s", produto.id, e)

                principal_url = next((item["url"] for item in fotos_enviadas if item.get("principal")), None)
                principal_url = principal_url or (fotos_enviadas[0]["url"] if fotos_enviadas else None)
                produto.foto_url = principal_url
                produto.fotos.clear()
                for ordem, item in enumerate(fotos_enviadas):
                    produto.fotos.append(ProdutoFoto(
                        url=item["url"],
                        eh_principal=item["url"] == principal_url,
                        ordem=ordem,
                    ))
                produto.atualizado_em = now_local()

            # ============================================================
            # SINCRONIZAR GALERIA DE VÍDEOS E MOVER TEMPORÁRIOS NO R2
            # ============================================================
            if videos_enviados is not None:
                from app.utils.r2_helpers import CDN_URL
                for item in videos_enviados:
                    video_url = item["url"]
                    if "produtos/videos/temp/" not in video_url:
                        continue
                    try:
                        from app.produtos.routes.utils import _r2_client, _r2_bucket_publico
                        client = _r2_client()
                        bucket = _r2_bucket_publico()
                        old_key = _key_from_url(video_url)
                        if old_key and "produtos/videos/temp/" in old_key:
                            new_key = old_key.replace("produtos/videos/temp/", f"produtos/videos/{produto.id}/")
                            client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": old_key}, Key=new_key)
                            client.delete_object(Bucket=bucket, Key=old_key)
                            item["url"] = f"{CDN_URL}/{new_key}"
                    except Exception as e:
                        current_app.logger.error("Erro ao migrar vídeo do produto %s: %s", produto.id, e)
                produto.videos.clear()
                for ordem, item in enumerate(videos_enviados):
                    produto.videos.append(ProdutoVideo(url=item["url"], titulo=item.get("titulo") or None, ordem=ordem))
                produto.atualizado_em = now_local()

            # ============================================================
            # SINCRONIZAR TOUR 360 E MOVER FRAMES TEMPORÁRIOS NO R2
            # ============================================================
            if tour360_enviado is not None:
                from app.utils.r2_helpers import CDN_URL
                frames_definitivos = []
                for frame_url in tour360_enviado["frames"]:
                    if "produtos/tours360/temp/" in frame_url:
                        try:
                            from app.produtos.routes.utils import _r2_client, _r2_bucket_publico
                            client = _r2_client()
                            bucket = _r2_bucket_publico()
                            old_key = _key_from_url(frame_url)
                            if old_key and "produtos/tours360/temp/" in old_key:
                                new_key = old_key.replace("produtos/tours360/temp/", f"produtos/tours360/{produto.id}/")
                                client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": old_key}, Key=new_key)
                                client.delete_object(Bucket=bucket, Key=old_key)
                                frame_url = f"{CDN_URL}/{new_key}"
                        except Exception as e:
                            current_app.logger.error("Erro ao migrar frame 360 do produto %s: %s", produto.id, e)
                    frames_definitivos.append(frame_url)
                if frames_definitivos:
                    if not produto.tour360:
                        produto.tour360 = ProdutoTour360()
                    produto.tour360.titulo = tour360_enviado["titulo"] or None
                    produto.tour360.ativo = tour360_enviado["ativo"]
                    produto.tour360.frames = frames_definitivos
                else:
                    produto.tour360 = None
                produto.atualizado_em = now_local()

            if acessorios_ids is not None:
                produto.acessorios = Produto.query.filter(
                    Produto.id.in_(acessorios_ids), Produto.id != produto.id
                ).order_by(Produto.nome.asc()).all()
                produto.atualizado_em = now_local()
            # ============================================================

            registros = []
            if not produto_id:
                registros.append(ProdutoHistorico(
                    produto_id=produto.id, 
                    campo="__acao__", 
                    valor_novo="Criação de produto",
                    usuario_id=getattr(current_user, "id", None), 
                    usuario_nome=getattr(current_user, "nome", None), 
                    data_modificacao=datetime.utcnow()
                ))

            depois = {c: getattr(produto, c, None) for c in campos_auditados}
            for campo in campos_auditados:
                a, d = antes.get(campo), depois.get(campo)
                if str(a) != str(d):
                    registros.append(ProdutoHistorico(
                        produto_id=produto.id, 
                        campo=campo, 
                        valor_antigo=str(a) if a is not None else None,
                        valor_novo=str(d) if d is not None else None, 
                        usuario_id=getattr(current_user, "id", None), 
                        usuario_nome=getattr(current_user, "nome", None), 
                        data_modificacao=datetime.utcnow()
                    ))

            if registros: 
                db.session.add_all(registros)
            
            db.session.commit()
            _LIST_CACHE.clear()
            flash("✅ Produto salvo com sucesso!", "success")
            return redirect(url_for("produtos.index"))

        except ValueError as ve:
            db.session.rollback()
            current_app.logger.error(f"Erro de validação ao salvar produto: {ve}")
            flash(f"❌ Erro de validação: {str(ve)}", "danger")
        except IntegrityError as ie:
            db.session.rollback()
            # Trata erro de chave única (código duplicado)
            if "duplicate key" in str(ie).lower() or "unique constraint" in str(ie).lower():
                if "codigo" in str(ie).lower() or "ix_produtos_codigo" in str(ie).lower():
                    flash(f"❌ Erro: Já existe um produto cadastrado com o código '{produto.codigo}'. Por favor, use um código único.", "danger")
                else:
                    flash(f"❌ Erro: Dados duplicados encontrados. Verifique se este produto já existe.", "danger")
            else:
                current_app.logger.error(f"Erro de integridade ao salvar produto: {ie}", exc_info=True)
                flash(f"❌ Erro ao salvar produto: Dados inválidos ou duplicados.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar produto: {e}", exc_info=True)
            flash(f"❌ Erro ao salvar produto: {str(e)}", "danger")

    if getattr(produto, "atualizado_em", None):
        try:
            fuso_fortaleza = pytz.timezone("America/Fortaleza")
            if produto.atualizado_em.tzinfo is None:
                produto.atualizado_em = produto.atualizado_em.replace(tzinfo=timezone.utc)
            produto.atualizado_em_local = produto.atualizado_em.astimezone(fuso_fortaleza)
        except Exception:
            produto.atualizado_em_local = produto.atualizado_em

    foto_proxy = None
    if produto and produto.foto_url:
        key = _key_from_url(produto.foto_url)
        foto_proxy = url_for('main.imagem_proxy', key=key) if key else produto.foto_url

    return render_template(
        "produtos/form/produto_form.html",
        produto=produto,
        foto_proxy=foto_proxy,
        categorias=categorias, marcas=marcas, calibres=calibres, tipos=tipos, funcionamentos=funcionamentos, produtos_para_acessorios=produtos_para_acessorios,
    )

# ============================================================
# EXCLUIR PRODUTO
# ============================================================
@produtos_bp.route("/<int:produto_id>/excluir", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    """
    Rota para excluir um produto específico.
    
    - Valida se o produto existe
    - Tenta excluir o produto do banco de dados
    - Limpa o cache de listagem
    - Retorna mensagens de sucesso ou erro detalhadas
    """
    try:
        produto = Produto.query.get_or_404(produto_id)
        nome_produto = produto.nome
        codigo_produto = produto.codigo
        
        db.session.delete(produto)
        db.session.commit()
        _LIST_CACHE.clear()
        
        flash(f"🗑️ Produto '{nome_produto}' (Código: {codigo_produto}) foi excluído com sucesso!", "success")
        current_app.logger.info(f"Produto {produto_id} ({nome_produto}) excluído por {current_user.nome if hasattr(current_user, 'nome') else 'usuário desconhecido'}")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir produto {produto_id}: {e}", exc_info=True)
        flash(f"❌ Erro ao excluir produto: {str(e)}", "danger")
    
    return redirect(url_for("produtos.index"))

# ============================================================
# VISUALIZAR PRODUTO (AJAX)
# ============================================================
@produtos_bp.route("/<int:produto_id>/visualizar", methods=["GET"])
@login_required
def visualizar_produto(produto_id):
    produto = Produto.query.options(
        joinedload(Produto.categoria), joinedload(Produto.marca_rel),
        joinedload(Produto.calibre_rel), joinedload(Produto.tipo_rel),
        joinedload(Produto.funcionamento_rel)
    ).filter_by(id=produto_id).first_or_404()

    def currency(val):
        try: v = float(val or 0)
        except: v = 0.0
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    url_imagem = "/static/img/placeholder.jpg"
    if produto.foto_url:
        key = _key_from_url(produto.foto_url)
        if key: url_imagem = url_for('main.imagem_proxy', key=key)

    valor_base = float(produto.preco_final or produto.preco_a_vista or 0.0)
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    linhas_raw = parc.gerar_linhas_parcelas(valor_base, taxas)

    parcelas_fmt = []
    parcela_12x_val = None
    for l in linhas_raw:
        rot = l.get("rotulo") or ""
        parcela_val = l.get("parcela") or 0
        total_val = l.get("total") or 0
        parcelas_fmt.append({"rotulo": rot, "parcela": currency(parcela_val), "total": currency(total_val)})
        if rot == "12x": parcela_12x_val = parcela_val

    parcelado_label = f"12x de {currency(parcela_12x_val)}" if parcela_12x_val is not None else "-"

    return {
        "id": produto.id, "codigo": produto.codigo or "-", "nome": produto.nome, "descricao": produto.descricao or "",
        "foto_url": url_imagem,
        "categoria": produto.categoria.nome if produto.categoria else "-",
        "marca": produto.marca_rel.nome if produto.marca_rel else "-",
        "calibre": produto.calibre_rel.nome if produto.calibre_rel else "-",
        "tipo": produto.tipo_rel.nome if produto.tipo_rel else "-",
        "funcionamento": produto.funcionamento_rel.nome if produto.funcionamento_rel else "-",
        "preco_avista": currency(valor_base), "parcelado_label": parcelado_label, "parcelas": parcelas_fmt,
    }
