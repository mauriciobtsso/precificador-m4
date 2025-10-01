from app.models import Produto
from app import db

def test_listar_produtos_vazio(client):
    resp = client.get("/produtos/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Nenhum produto cadastrado" in text or "produtos" in text.lower()

def test_criar_editar_excluir_produto(client, app):
    # Criar
    resp = client.post("/produtos/novo", data={
        "sku": "TEST123",
        "nome": "Produto Teste",
        "preco_fornecedor": "1000",
        "desconto_fornecedor": "0",
        "margem": "20",
        "ipi": "10",
        "ipi_tipo": "%",
        "difal": "5",
        "frete": "50",
        "imposto_venda": "0"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Produto salvo com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        produto = Produto.query.filter_by(sku="TEST123").first()
        assert produto is not None
        produto_id = produto.id

    # Editar
    resp = client.post(f"/produtos/editar/{produto_id}", data={
        "sku": "TEST123",
        "nome": "Produto Alterado",
        "preco_fornecedor": "1200",
        "margem": "25",
        "ipi": "12",
        "ipi_tipo": "%",
        "difal": "5",
        "frete": "70",
        "imposto_venda": "0"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Produto salvo com sucesso" in resp.get_data(as_text=True)

    # Excluir
    resp = client.get(f"/produtos/excluir/{produto_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert "Produto excluído com sucesso" in resp.get_data(as_text=True)
