from decimal import Decimal
from uuid import uuid4

from app import db
from app.carrinho.models import Pedido


def _create_order(status):
    public_id = str(uuid4())
    pedido = Pedido(
        public_id=public_id,
        nome_cliente="Cliente Sintético",
        email_cliente="cliente-teste@example.test",
        documento="00000000000",
        telefone="86000000000",
        cep="64000000",
        logradouro="Rua de Teste",
        numero="1",
        bairro="Centro",
        cidade="Teresina",
        estado="PI",
        total_produtos=Decimal("123.45"),
        total_frete=Decimal("0.00"),
        total_pedido=Decimal("123.45"),
        total_cobrado=Decimal("123.45"),
        forma_pagamento="pix",
        parcelas=1,
        status=status,
    )
    db.session.add(pedido)
    db.session.commit()
    return pedido


def test_paid_order_emits_minimal_purchase_event_without_customer_data(app, client):
    with app.app_context():
        pedido = _create_order("pago")
        public_id = pedido.public_id

    try:
        response = client.get(f"/carrinho/sucesso/{public_id}")
        body = response.get_data(as_text=True)

        assert response.status_code == 200
        assert "event: 'purchase'" in body
        assert public_id in body
        assert "123.45" in body
        assert "currency: 'BRL'" in body
        assert "Pedido M4 Tática" in body
        assert "cliente-teste@example.test" not in body
        assert "00000000000" not in body
        assert "86000000000" not in body
        assert "dataLayer" in body
    finally:
        with app.app_context():
            Pedido.query.filter_by(public_id=public_id).delete()
            db.session.commit()


def test_unpaid_order_does_not_emit_purchase_event(app, client):
    with app.app_context():
        pedido = _create_order("pendente")
        public_id = pedido.public_id

    try:
        response = client.get(f"/carrinho/sucesso/{public_id}")
        body = response.get_data(as_text=True)

        assert response.status_code == 200
        assert "event: 'purchase'" not in body
    finally:
        with app.app_context():
            Pedido.query.filter_by(public_id=public_id).delete()
            db.session.commit()
