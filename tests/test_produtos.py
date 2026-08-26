from app.produtos.models import Produto
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import TipoProduto
from app import db


def test_listar_produtos_vazio(client):
    resp = client.get("/produtos/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Nenhum produto cadastrado" in text or "produtos" in text.lower()


def test_criar_editar_excluir_produto(client, app):
    with app.app_context():
        categoria = CategoriaProduto(nome="Categoria Teste")
        tipo = TipoProduto(nome="Tipo Teste")
        db.session.add_all([categoria, tipo])
        db.session.commit()
        categoria_id = categoria.id
        tipo_id = tipo.id

    payload = {
        "codigo": "TEST123",
        "nome": "Produto Teste",
        "categoria_id": str(categoria_id),
        "tipo_id": str(tipo_id),
        "preco_fornecedor": "1000",
        "desconto_fornecedor": "0",
        "margem": "20",
        "ipi": "10",
        "ipi_tipo": "%",
        "difal": "5",
        "frete": "50",
        "imposto_venda": "0",
    }

    # Criar
    resp = client.post("/produtos/novo", data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert "Produto salvo com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        produto = Produto.query.filter_by(codigo="TEST123").first()
        assert produto is not None
        produto_id = produto.id

    # Editar
    payload["nome"] = "Produto Alterado"
    payload["preco_fornecedor"] = "1200"
    payload["margem"] = "25"
    payload["ipi"] = "12"
    payload["frete"] = "70"
    resp = client.post(f"/produtos/{produto_id}/editar", data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert "Produto salvo com sucesso" in resp.get_data(as_text=True)

    # Excluir — a rota atual aceita POST, como o formulário administrativo.
    resp = client.post(f"/produtos/{produto_id}/excluir", follow_redirects=True)
    assert resp.status_code == 200
    assert "foi excluído com sucesso" in resp.get_data(as_text=True)
