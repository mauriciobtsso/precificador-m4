from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app import db
from app.carrinho.logic import PagarmeOrchestrator
from app.carrinho.frete_quotes import cart_fingerprint, issue_quote, validate_quote
from app.carrinho.models import Carrinho, CarrinhoItem, Pedido
from app.carrinho.payment import calcular_snapshot_pix, construir_payload_pix, to_cents
from app.models import Configuracao
from app.produtos.models import Produto


def _set_pagarme_secret():
    config = Configuracao.query.filter_by(chave="integ_pagarme_secret_key").first()
    if config:
        config.valor = "sk_test_placeholder"
    else:
        db.session.add(Configuracao(chave="integ_pagarme_secret_key", valor="sk_test_placeholder"))


def _pedido(public_id, total="12.00", email=None):
    public_id = public_id or str(uuid4())
    return Pedido(
        public_id=public_id,
        nome_cliente="Cliente Teste",
        email_cliente=email or public_id + "@example.test",
        documento="12345678901",
        telefone="86912345678",
        cep="64000000",
        logradouro="Rua Central",
        numero="1",
        bairro="Centro",
        cidade="Teresina",
        estado="PI",
        total_produtos=Decimal(total),
        total_frete=Decimal("0.00"),
        total_pedido=Decimal(total),
        total_cobrado=Decimal(total),
        forma_pagamento="pix",
        parcelas=1,
        status="pendente",
    )


def test_snapshot_pix_aplica_desconto_por_unidade_e_preserva_frete():
    produto = SimpleNamespace(nome="Produto teste", nome_comercial=None, codigo="P-1", id=1)
    item = SimpleNamespace(produto=produto, quantidade=3, preco_unitario_no_momento=Decimal("10.01"))
    snapshot = calcular_snapshot_pix([item], Decimal("5.00"))

    # 5% sobre R$10,01 arredonda a R$9,51 por unidade; frete fica integral.
    assert snapshot["total_produtos"] == Decimal("30.03")
    assert snapshot["total_produtos_pix"] == Decimal("28.53")
    assert snapshot["total_frete"] == Decimal("5.00")
    assert snapshot["total_base"] == Decimal("35.03")
    assert snapshot["desconto_aplicado"] == Decimal("1.50")
    assert snapshot["total_cobrado"] == Decimal("33.53")
    assert snapshot["valor_parcela"] == Decimal("33.53")


def test_snapshot_zero_continua_renderizavel_para_previa_sem_itens_cobraveis():
    item = SimpleNamespace(quantidade=1, preco_unitario_no_momento=Decimal("0.00"))
    snapshot = calcular_snapshot_pix([item], Decimal("0.00"))
    assert snapshot["total_produtos_pix"] == Decimal("0.00")
    assert snapshot["total_cobrado"] == Decimal("0.00")


def test_payload_pix_reflete_exatamente_snapshot():
    produto = SimpleNamespace(nome="Produto teste", nome_comercial=None, codigo="P-1", id=1)
    item = SimpleNamespace(produto=produto, quantidade=2, preco_unitario_no_momento=Decimal("10.00"))
    snapshot = calcular_snapshot_pix([item], Decimal("5.00"))
    pedido = SimpleNamespace(public_id="pedido-publico-1")
    dados = {
        "nome": "Cliente Teste", "email": "cliente@example.test", "documento": "12345678901",
        "telefone": "86912345678", "cep": "64000000", "logradouro": "Rua Central",
        "numero": "123", "bairro": "Centro", "cidade": "Teresina", "estado": "PI",
    }

    payload = construir_payload_pix(pedido, snapshot, dados, "Entrega")
    itens_centavos = sum(row["amount"] * row["quantity"] for row in payload["items"])
    assert payload["code"] == pedido.public_id
    assert payload["payments"][0]["payment_method"] == "pix"
    assert payload["payments"][0]["pix"]["expires_in"] == 3600
    assert payload["customer"]["document"] == "12345678901"
    assert payload["customer"]["address"]["state"] == "BR-PI"
    assert itens_centavos + payload["shipping"]["amount"] == to_cents(snapshot["total_cobrado"])
    assert payload["items"][0]["amount"] == 950


def test_cliente_pagarme_usa_basic_auth_e_endpoint_oficial():
    chamada = {}

    class Response:
        status_code = 201
        def json(self):
            return {"id": "or_test", "status": "pending"}

    class HTTP:
        @staticmethod
        def request(method, url, **kwargs):
            chamada.update(method=method, url=url, **kwargs)
            return Response()

    resultado = PagarmeOrchestrator("sk_test_placeholder", http=HTTP).criar_pedido({"items": [], "payments": []})
    assert resultado["id"] == "or_test"
    assert chamada["method"] == "POST"
    assert chamada["url"] == "https://api.pagar.me/core/v5/orders"
    assert chamada["auth"] == ("sk_test_placeholder", "")
    assert "card_number" not in str(chamada["json"])


def test_cotacao_frete_assinada_expira_e_nao_aceita_valor_ou_carrinho_alterados():
    fingerprint = "cart-fingerprint"
    token, expires = issue_quote("64000000", "frete-1", "Transportadora – Econômico", Decimal("5.00"), "Prazo: 3 dias", fingerprint, "test-secret", now=1000)
    assert validate_quote("64000000", "frete-1", "Transportadora – Econômico", Decimal("5.00"), "Prazo: 3 dias", fingerprint, token, expires, "test-secret", now=1010)
    assert not validate_quote("64000000", "frete-1", "Transportadora – Econômico", Decimal("0.00"), "Prazo: 3 dias", fingerprint, token, expires, "test-secret", now=1010)
    assert not validate_quote("64000000", "frete-1", "Transportadora – Econômico", Decimal("5.00"), "Prazo: 3 dias", "other-cart", token, expires, "test-secret", now=1010)
    assert not validate_quote("64000000", "frete-1", "Transportadora – Econômico", Decimal("5.00"), "Prazo: 3 dias", fingerprint, token, expires, "test-secret", now=2000)


def test_endpoint_nao_salva_frete_sem_assinatura(client):
    response = client.post("/carrinho/api/frete/salvar", json={
        "valor": 0, "nome": "Entrega falsificada", "prazo": "", "cep": "64000000",
    })
    assert response.status_code == 400


def test_cotacao_melhor_envio_assina_opcoes_e_bloqueia_preco_adulterado(client, app, monkeypatch):
    with app.app_context():
        cart_session = "quote-cart-" + uuid4().hex
        produto = Produto(codigo="FRETE-" + uuid4().hex[:8], nome="Produto frete", preco_a_vista=Decimal("20.00"))
        config = Configuracao.query.filter_by(chave="integ_melhorenvio_token").first()
        if config:
            config.valor = "test-token"
        else:
            db.session.add(Configuracao(chave="integ_melhorenvio_token", valor="test-token"))
        db.session.add(produto)
        db.session.flush()
        carrinho = Carrinho(session_id=cart_session, usuario_id=None, cliente_id=None)
        carrinho.items.append(CarrinhoItem(produto_id=produto.id, quantidade=1, preco_unitario_no_momento=Decimal("20.00")))
        db.session.add(carrinho)
        db.session.commit()

    class FakeFrete:
        def __init__(self, token, sandbox=False):
            assert token == "test-token"
        def calcular_frete(self, origem, destino, items):
            return [{
                "id": 17, "name": "Econômico", "price": 7.75,
                "company": {"name": "Transportadora"},
                "delivery_range": {"min": 2, "max": 3},
            }]

    monkeypatch.setattr("app.carrinho.routes.MelhorEnvioService", FakeFrete)
    with client.session_transaction() as sess:
        sess["cart_session_id"] = cart_session

    cotacao_response = client.post("/carrinho/api/frete/calcular", json={"cep": "79000000"})
    assert cotacao_response.status_code == 200
    opcao = cotacao_response.get_json()["opcoes"][0]
    payload = {
        "valor": opcao["price"], "nome": opcao["quote_name"], "prazo": opcao["quote_prazo"],
        "cep": "79000000", "quote_id": opcao["quote_id"],
        "quote_token": opcao["quote_token"], "quote_expires_at": opcao["quote_expires_at"],
    }
    assert client.post("/carrinho/api/frete/salvar", json=payload).status_code == 200
    payload["valor"] = 0
    adulterada = client.post("/carrinho/api/frete/salvar", json=payload)
    assert adulterada.status_code == 400

    with app.app_context():
        config = Configuracao.query.filter_by(chave="integ_melhorenvio_token").one()
        config.valor = ""
        db.session.commit()
    retirada = client.post("/carrinho/api/frete/calcular", json={"cep": "64000000"})
    assert retirada.status_code == 200
    retirada_opcao = retirada.get_json()["opcoes"][0]
    assert retirada_opcao["custom"] is True
    assert retirada_opcao["quote_token"]


def test_checkout_recusa_cartao_no_servidor(client, app):
    response = client.post("/carrinho/checkout/processar", json={"metodo_pagamento": "credit_card"})
    assert response.status_code == 409
    assert "temporariamente desabilitado" in response.get_json()["message"]
    with app.app_context():
        assert Pedido.query.filter_by(forma_pagamento="credit_card").count() == 0


def test_checkout_pix_persiste_snapshot_qr_e_limpa_carrinho(client, app, monkeypatch):
    with app.app_context():
        produto = Produto(codigo="PX-" + uuid4().hex[:12], nome="Produto PIX", preco_a_vista=Decimal("10.00"), visivel_loja=True)
        cart_session = "cart-" + uuid4().hex
        carrinho = Carrinho(session_id=cart_session, usuario_id=None, cliente_id=None)
        db.session.add(produto)
        _set_pagarme_secret()
        db.session.flush()
        carrinho.items.append(CarrinhoItem(produto_id=produto.id, quantidade=2, preco_unitario_no_momento=Decimal("10.00")))
        db.session.add(carrinho)
        db.session.commit()
        email = "pix-" + uuid4().hex + "@example.test"
        frete_id = "frete-teste"
        frete_nome = "Entrega teste"
        frete_prazo = "Prazo: até 2 dias úteis"
        cart_hash = cart_fingerprint(carrinho)
        frete_token, frete_exp = issue_quote(
            "64000000", frete_id, frete_nome, Decimal("5.00"), frete_prazo,
            cart_hash, app.secret_key,
        )

    class FakeGateway:
        def __init__(self, api_key):
            assert api_key == "sk_test_placeholder"
        def criar_pedido(self, payload):
            amount = sum(item["amount"] * item["quantity"] for item in payload["items"])
            amount += payload.get("shipping", {}).get("amount", 0)
            return {
                "id": "or_test_pix", "code": payload["code"], "amount": amount, "status": "pending",
                "charges": [{"last_transaction": {
                    "transaction_type": "pix", "qr_code": "000201PIX_TESTE",
                    "qr_code_url": "https://api.pagar.me/teste/qr.png",
                    "expires_at": "2026-09-29T13:00:00Z",
                }}],
            }

    monkeypatch.setattr("app.carrinho.checkout_service.PagarmeOrchestrator", FakeGateway)
    monkeypatch.setattr("app.carrinho.checkout_service.registrar_notificacao", lambda **kwargs: None)
    monkeypatch.setattr("app.utils.email_service.enviar_email_novo_pedido", lambda pedido: True)
    checkout_key = "checkout-" + uuid4().hex[:24]
    with client.session_transaction() as sess:
        sess["cart_session_id"] = cart_session
        sess["frete_valor"] = 5.00
        sess["frete_nome"] = "Entrega teste"
        sess["frete_prazo"] = frete_prazo
        sess["frete_cep"] = "64000000"
        sess["frete_quote_id"] = frete_id
        sess["frete_quote_token"] = frete_token
        sess["frete_quote_expires_at"] = frete_exp
        sess["loja_checkout_key"] = checkout_key

    checkout_page = client.get("/carrinho/checkout")
    assert checkout_page.status_code == 200
    assert "5% de desconto nos produtos" in checkout_page.get_data(as_text=True)
    assert "checkout_key" in checkout_page.get_data(as_text=True)

    response = client.post("/carrinho/checkout/processar", json={
        "metodo_pagamento": "pix", "checkout_key": checkout_key,
        "nome": "Cliente Teste", "email": email, "documento": "12345678901",
        "telefone": "(86) 91234-5678", "cep": "64000000", "logradouro": "Rua Central",
        "numero": "123", "bairro": "Centro", "cidade": "Teresina", "uf": "PI",
    })
    assert response.status_code == 200
    result = response.get_json()
    assert result["success"] is True
    assert result["redirect"].endswith(result["pedido_id"])
    success_page = client.get(result["redirect"])
    assert success_page.status_code == 200
    assert "000201PIX_TESTE" in success_page.get_data(as_text=True)

    with app.app_context():
        pedido = Pedido.query.filter_by(email_cliente=email).one()
        assert pedido.total_produtos == Decimal("20.00")
        assert pedido.total_frete == Decimal("5.00")
        assert pedido.total_pedido == Decimal("25.00")
        assert pedido.desconto_aplicado == Decimal("1.00")
        assert pedido.total_cobrado == Decimal("24.00")
        assert pedido.taxa_aplicada == Decimal("0.0000")
        assert pedido.parcelas == 1
        assert pedido.valor_parcela == Decimal("24.00")
        assert pedido.pagarme_id == "or_test_pix"
        assert pedido.pagarme_pix_qr_code == "000201PIX_TESTE"
        assert Carrinho.query.filter_by(session_id=cart_session).one().items == []


def test_webhook_consulta_api_e_confere_valor_antes_de_marcar_pago(client, app, monkeypatch):
    with app.app_context():
        public_id = "webhook-" + uuid4().hex
        pedido = _pedido(public_id)
        db.session.add(pedido)
        _set_pagarme_secret()
        db.session.commit()
        pedido_id = pedido.id

    class FakeGateway:
        def __init__(self, api_key):
            assert api_key == "sk_test_placeholder"
        def obter_pedido(self, pagarme_id):
            return {"id": pagarme_id, "code": public_id, "amount": 1200, "status": "paid", "paid_at": "2026-09-29T13:01:00Z"}

    monkeypatch.setattr("app.carrinho.checkout_service.PagarmeOrchestrator", FakeGateway)
    monkeypatch.setattr("app.utils.email_service.enviar_email_status_pedido", lambda pedido: True)
    response = client.post("/carrinho/webhook/pagarme", json={"type": "order.paid", "data": {"id": "or_webhook"}})
    assert response.status_code == 200
    with app.app_context():
        pedido = db.session.get(Pedido, pedido_id)
        assert pedido.status == "pago"
        assert pedido.pagarme_id == "or_webhook"
        assert pedido.pago_em is not None


def test_webhook_rejeita_valor_divergente(client, app, monkeypatch):
    with app.app_context():
        public_id = "mismatch-" + uuid4().hex
        pedido = _pedido(public_id)
        db.session.add(pedido)
        _set_pagarme_secret()
        db.session.commit()
        pedido_id = pedido.id

    class FakeGateway:
        def __init__(self, api_key):
            pass
        def obter_pedido(self, pagarme_id):
            return {"id": pagarme_id, "code": public_id, "amount": 500, "status": "paid"}

    monkeypatch.setattr("app.carrinho.checkout_service.PagarmeOrchestrator", FakeGateway)
    response = client.post("/carrinho/webhook/pagarme", json={"data": {"id": "or_fake"}})
    assert response.status_code == 409
    with app.app_context():
        assert db.session.get(Pedido, pedido_id).status == "pendente"
