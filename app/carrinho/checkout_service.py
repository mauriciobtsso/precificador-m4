"""Orquestra a cobrança PIX da loja sem interferir em checkout interno."""
from datetime import datetime
import hmac

from flask import current_app, session, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.alertas.notificacoes import registrar_notificacao
from app.models import Configuracao
from app.utils.datetime import now_local
from .logic import PagarmeAPIError, PagarmeOrchestrator
from .frete_quotes import cart_fingerprint, validate_quote
from .models import Pedido, PedidoItem
from .payment import (
    calcular_snapshot_pix,
    construir_payload_pix,
    extrair_dados_pix,
    status_local_pagarme,
    to_cents,
)


def _secret_key():
    config = Configuracao.query.filter_by(chave="integ_pagarme_secret_key").first()
    return str(config.valor or "").strip() if config else ""


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _notify_new_order(pedido, cliente_id=None):
    try:
        registrar_notificacao(
            tipo="venda",
            nivel="info",
            mensagem=(
                f"Novo pedido #{pedido.id} via PIX (R$ "
                f"{pedido.total_cobrado:,.2f})"
            ),
            cliente_id=cliente_id,
        )
    except Exception:
        current_app.logger.exception("Falha ao registrar notificação do pedido PIX")


def _send_new_order_email(pedido):
    try:
        from app.utils.email_service import enviar_email_novo_pedido
        enviar_email_novo_pedido(pedido)
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail do pedido PIX")


def _send_status_email(pedido):
    try:
        from app.utils.email_service import enviar_email_status_pedido
        enviar_email_status_pedido(pedido)
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail de atualização do pedido")


def _response_for_order(pedido, message=None):
    result = {
        "success": True,
        "pedido_id": pedido.public_id,
        "redirect": url_for("carrinho.sucesso", public_id=pedido.public_id),
    }
    if message:
        result["message"] = message
    return result


def processar_checkout_pix(data, carrinho, cliente=None):
    """Valida e cria somente PIX; cartão fica fail-closed até confirmar a conta."""
    def texto(key):
        return str(data.get(key) or "").strip()

    metodo = (texto("metodo_pagamento") or "pix").lower()
    if metodo != "pix":
        return {
            "success": False,
            "message": "Pagamento por cartão está temporariamente desabilitado até confirmar o tipo da conta Pagar.me.",
        }, 409
    if not carrinho or not carrinho.items:
        return {"success": False, "message": "Carrinho vazio."}, 400

    checkout_key = texto("checkout_key")
    checkout_key_sessao = str(session.get("loja_checkout_key") or "")
    if not checkout_key or not checkout_key_sessao or not hmac.compare_digest(checkout_key, checkout_key_sessao):
        return {"success": False, "message": "Checkout expirado. Atualize a página e tente novamente."}, 409

    pedido_existente = Pedido.query.filter_by(checkout_key=checkout_key).first()
    if pedido_existente:
        if pedido_existente.status == "cancelado" and not pedido_existente.pagarme_id:
            session.pop("loja_checkout_key", None)
            return {"success": False, "message": "A tentativa anterior foi recusada. Atualize o checkout para gerar uma nova tentativa."}, 409
        if pedido_existente.pagarme_id:
            return _response_for_order(pedido_existente), 200
        return {
            "success": False,
            "message": f"O pedido #{pedido_existente.id} já está em processamento. Não tente pagar novamente; aguarde a confirmação do PIX.",
        }, 409

    if cliente:
        nome_cliente = (cliente.nome or "").strip()
        email_cliente = (cliente.email_login or "").strip().lower()
        documento = "".join(ch for ch in str(cliente.documento or "") if ch.isdigit())
        cliente_id = cliente.id
        usuario_id = None
    else:
        nome_cliente = texto("nome")
        email_cliente = texto("email").lower()
        documento = "".join(ch for ch in texto("documento") if ch.isdigit())
        cliente_id = None
        try:
            from flask_login import current_user
            usuario_id = current_user.id if current_user.is_authenticated else None
        except Exception:
            usuario_id = None

    telefone = texto("telefone")
    telefone_digits = "".join(ch for ch in telefone if ch.isdigit())
    cep = "".join(ch for ch in texto("cep") if ch.isdigit())
    logradouro = texto("logradouro")
    numero = texto("numero")
    bairro = texto("bairro")
    cidade = texto("cidade")
    estado = texto("uf").upper()
    if not all([nome_cliente, email_cliente, documento, cep, logradouro, numero, bairro, cidade, estado, telefone]):
        return {"success": False, "message": "Preencha todos os campos obrigatórios."}, 400
    if "@" not in email_cliente or len(email_cliente) > 64:
        return {"success": False, "message": "Informe um e-mail válido."}, 400
    if len(documento) not in (11, 14):
        return {"success": False, "message": "Informe um CPF ou CNPJ válido."}, 400
    if len(telefone_digits) not in (10, 11):
        return {"success": False, "message": "Informe um telefone com DDD válido."}, 400
    if len(cep) != 8 or len(estado) != 2:
        return {"success": False, "message": "Confira o CEP e a UF informados."}, 400

    nome_frete = str(session.get("frete_nome") or "").strip()
    cep_frete = "".join(ch for ch in str(session.get("frete_cep") or "") if ch.isdigit())
    if not nome_frete:
        return {"success": False, "message": "Selecione uma opção de frete ou retirada na loja antes de finalizar."}, 400
    if cep_frete != cep:
        return {"success": False, "message": "O frete precisa ser recalculado para o CEP informado."}, 400
    try:
        valor_frete = float(session.get("frete_valor") or 0)
    except (TypeError, ValueError):
        return {"success": False, "message": "Valor de frete inválido."}, 400
    if valor_frete < 0:
        return {"success": False, "message": "Valor de frete inválido."}, 400
    cotacao_valida = validate_quote(
        cep,
        session.get("frete_quote_id"),
        nome_frete,
        valor_frete,
        session.get("frete_prazo"),
        cart_fingerprint(carrinho),
        session.get("frete_quote_token"),
        session.get("frete_quote_expires_at"),
        current_app.secret_key,
    )
    if not cotacao_valida:
        return {"success": False, "message": "A cotação do frete expirou ou mudou com o carrinho. Recalcule o frete antes de finalizar."}, 400
    if "retirar na loja" in nome_frete.lower():
        config_cep = Configuracao.query.filter_by(chave="integ_melhorenvio_cep_origem").first()
        cep_origem = config_cep.valor if config_cep and config_cep.valor else "64000000"
        origem = "".join(ch for ch in str(cep_origem) if ch.isdigit())
        if len(origem) != 8 or origem[:5] != cep[:5]:
            return {"success": False, "message": "A retirada na loja está disponível apenas para CEPs da cidade de origem."}, 400
        valor_frete = 0

    api_key = _secret_key()
    if not api_key:
        return {"success": False, "message": "O pagamento PIX ainda não está configurado. Entre em contato com a loja."}, 503

    try:
        snapshot = calcular_snapshot_pix(carrinho.items, valor_frete)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}, 400
    if not snapshot["linhas"] or snapshot["total_produtos_pix"] <= 0 or snapshot["total_cobrado"] <= 0:
        return {"success": False, "message": "O pedido precisa conter ao menos um produto com valor maior que zero."}, 400

    pedido = Pedido(
        usuario_id=usuario_id,
        cliente_id=cliente_id,
        nome_cliente=nome_cliente[:100],
        email_cliente=email_cliente[:100],
        documento=documento,
        telefone=telefone[:20],
        cep=cep,
        logradouro=logradouro[:255],
        numero=numero[:20],
        bairro=bairro[:100],
        cidade=cidade[:100],
        estado=estado,
        total_produtos=snapshot["total_produtos"],
        total_frete=snapshot["total_frete"],
        total_pedido=snapshot["total_base"],
        total_cobrado=snapshot["total_cobrado"],
        taxa_aplicada=snapshot["taxa_aplicada"],
        desconto_aplicado=snapshot["desconto_aplicado"],
        valor_parcela=snapshot["valor_parcela"],
        forma_pagamento="pix",
        parcelas=1,
        checkout_key=checkout_key,
        status="pendente",
    )
    db.session.add(pedido)
    try:
        db.session.flush()
        for item in carrinho.items:
            db.session.add(PedidoItem(
                pedido_id=pedido.id,
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                preco_unitario_historico=item.preco_unitario_no_momento,
            ))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        pedido_existente = Pedido.query.filter_by(checkout_key=checkout_key).first()
        if pedido_existente and pedido_existente.pagarme_id:
            return _response_for_order(pedido_existente), 200
        return {"success": False, "message": "Este checkout já está sendo processado; aguarde antes de tentar novamente."}, 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao persistir o pedido PIX antes da cobrança")
        return {"success": False, "message": "Não foi possível registrar o pedido."}, 500

    dados_cliente = {
        "nome": nome_cliente,
        "email": email_cliente,
        "documento": documento,
        "telefone": telefone_digits,
        "cep": cep,
        "logradouro": logradouro,
        "numero": numero,
        "bairro": bairro,
        "cidade": cidade,
        "estado": estado,
    }
    try:
        payload = construir_payload_pix(pedido, snapshot, dados_cliente, nome_frete)
        resposta = PagarmeOrchestrator(api_key).criar_pedido(payload)
    except PagarmeAPIError as exc:
        if not exc.ambiguous:
            pedido.status = "cancelado"
            db.session.commit()
            session.pop("loja_checkout_key", None)
            return {"success": False, "message": "O Pagar.me não aceitou a solicitação PIX. Confira os dados e tente novamente."}, 502
        current_app.logger.warning("Resposta ambígua ao criar pedido PIX interno #%s", pedido.id)
        _notify_new_order(pedido, cliente_id)
        return _response_for_order(
            pedido,
            "O pedido foi registrado, mas ainda não recebemos a confirmação do Pagar.me. Não tente pagar de novo; atualize esta página em alguns instantes.",
        ), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha inesperada ao preparar pedido PIX interno #%s", pedido.id)
        return {"success": False, "message": "Não foi possível iniciar o pagamento PIX."}, 500

    remote_id = str(resposta.get("id") or "").strip()
    remote_code = str(resposta.get("code") or "").strip()
    remote_amount = resposta.get("amount")
    pix = extrair_dados_pix(resposta)
    pedido.pagarme_id = remote_id or None
    if remote_code and remote_code != pedido.public_id:
        current_app.logger.error("Código do pedido Pagar.me diverge do pedido local #%s", pedido.id)
        pedido.pagarme_pix_qr_code = None
        pedido.pagarme_pix_qr_code_url = None
        db.session.commit()
        return _response_for_order(pedido, "O pedido aguarda conferência da loja; não pague um QR Code recebido fora desta página."), 200

    try:
        amount_matches = int(remote_amount) == to_cents(snapshot["total_cobrado"])
    except (TypeError, ValueError):
        amount_matches = False
    if not remote_id or not amount_matches:
        pedido.pagarme_pix_qr_code = None
        pedido.pagarme_pix_qr_code_url = None
        db.session.commit()
        current_app.logger.error("Resposta do Pagar.me sem ID ou com valor divergente no pedido local #%s", pedido.id)
        _notify_new_order(pedido, cliente_id)
        return _response_for_order(pedido, "O pagamento aguarda conferência do valor pela loja. Não tente pagar novamente."), 200

    pedido.status = status_local_pagarme(resposta.get("status"))
    pedido.pagarme_pix_qr_code = pix["codigo"]
    pedido.pagarme_pix_qr_code_url = pix["url"]
    pedido.pagarme_pix_expires_at = _parse_datetime(pix["expira_em"])
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao persistir resposta do Pagar.me no pedido #%s", pedido.id)
        return _response_for_order(pedido, "O pedido foi enviado ao Pagar.me; aguarde a atualização antes de tentar novamente."), 200

    if pix["codigo"] or pedido.status == "pago":
        for item in list(carrinho.items):
            db.session.delete(item)
        cart_cleared = True
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            cart_cleared = False
            current_app.logger.exception("Falha ao limpar carrinho após gerar PIX do pedido #%s", pedido.id)
        if cart_cleared:
            session.pop("loja_checkout_key", None)
            for key in (
                "frete_valor", "frete_nome", "frete_prazo", "frete_cep",
                "frete_quote_id", "frete_quote_token", "frete_quote_expires_at",
            ):
                session.pop(key, None)

    _notify_new_order(pedido, cliente_id)
    _send_new_order_email(pedido)
    return _response_for_order(pedido), 200


def processar_webhook_pagarme(payload):
    """Consulta o pedido na API autenticada antes de aceitar estado do webhook."""
    if not isinstance(payload, dict):
        return {"success": False, "message": "Payload inválido."}, 400
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    remote_id = str(data.get("id") or payload.get("id") or "").strip()
    if not remote_id:
        return {"success": False, "message": "ID do pedido ausente."}, 400
    api_key = _secret_key()
    if not api_key:
        return {"success": False, "message": "Gateway não configurado."}, 503

    try:
        remote = PagarmeOrchestrator(api_key).obter_pedido(remote_id)
    except PagarmeAPIError:
        current_app.logger.warning("Não foi possível validar o webhook Pagar.me para o recurso informado")
        return {"success": False, "message": "Não foi possível validar o pedido no gateway."}, 503

    if str(remote.get("id") or remote_id) != remote_id:
        return {"success": False, "message": "Resposta do gateway não corresponde ao evento."}, 400
    remote_code = str(remote.get("code") or "").strip()
    pedido = Pedido.query.filter_by(public_id=remote_code).first() if remote_code else None
    if not pedido:
        pedido = Pedido.query.filter_by(pagarme_id=remote_id).first()
    if not pedido:
        return {"success": False, "message": "Pedido local não encontrado."}, 404

    try:
        if int(remote.get("amount")) != to_cents(pedido.total_cobrado or pedido.total_pedido):
            current_app.logger.error("Valor do webhook Pagar.me divergente para pedido local #%s", pedido.id)
            return {"success": False, "message": "Valor do gateway não corresponde ao snapshot local."}, 409
    except (TypeError, ValueError):
        return {"success": False, "message": "Resposta do gateway sem valor verificável."}, 400

    previous_status = pedido.status
    previous_gateway_id = pedido.pagarme_id
    pedido.pagarme_id = remote_id
    pedido.status = status_local_pagarme(remote.get("status"))
    pix = extrair_dados_pix(remote)
    if pix["codigo"]:
        pedido.pagarme_pix_qr_code = pix["codigo"]
    if pix["url"]:
        pedido.pagarme_pix_qr_code_url = pix["url"]
    if pix["expira_em"]:
        pedido.pagarme_pix_expires_at = _parse_datetime(pix["expira_em"])
    if pedido.status == "pago" and not pedido.pago_em:
        pedido.pago_em = _parse_datetime(remote.get("paid_at")) or now_local()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao atualizar pedido local pelo webhook Pagar.me")
        return {"success": False, "message": "Não foi possível persistir o evento."}, 500

    if previous_status != pedido.status:
        _send_status_email(pedido)
    elif not previous_gateway_id and pedido.pagarme_pix_qr_code:
        _send_new_order_email(pedido)
    return {"success": True}, 200
