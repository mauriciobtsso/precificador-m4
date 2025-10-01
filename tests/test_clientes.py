from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente
from app import db

def test_listar_clientes_vazio(client):
    resp = client.get("/clientes/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Nenhum cliente cadastrado" in text or "clientes" in text.lower()

def test_criar_cliente_e_detalhe(client, app):
    with app.app_context():
        cliente = Cliente(nome="Cliente Teste")
        db.session.add(cliente)
        db.session.commit()
        cliente_id = cliente.id

    resp = client.get(f"/clientes/{cliente_id}")
    assert resp.status_code == 200
    assert "Cliente Teste" in resp.get_data(as_text=True)
