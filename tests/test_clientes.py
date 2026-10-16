from pathlib import Path

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


def test_lista_clientes_tem_layout_responsivo_sem_largura_minima_da_tabela(client, app):
    with app.app_context():
        cliente = Cliente(
            nome="Cliente com um nome comprido para validar a quebra de linha",
            documento="98765432100",
        )
        db.session.add(cliente)
        db.session.flush()
        db.session.add(
            ContatoCliente(
                cliente_id=cliente.id,
                tipo="email",
                valor="contato.com.nome.muito.longo@subdominio.exemplo.br",
            )
        )
        db.session.commit()

    response = client.get("/clientes/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'class="clientes-table-wrap d-none d-md-block"' in html
    assert "table-clientes-lista" in html
    assert 'class="clientes-mobile-wrap d-block d-md-none"' in html
    assert 'aria-label="Ver detalhes de Cliente com um nome comprido para validar a quebra de linha"' in html

    css_path = Path(__file__).resolve().parents[1] / "app/static/css/clientes.css"
    css = css_path.read_text(encoding="utf-8")
    assert "table-layout: fixed;" in css
    assert "overflow-wrap: anywhere;" in css
    assert ".clientes-pagination .pagination" in css


def test_cadastro_e_edicao_de_cliente_persistem_rg_e_orgao_emissor(client, app):
    response = client.get("/clientes/novo")
    assert response.status_code == 200
    assert 'name="rg"' in response.get_data(as_text=True)
    assert 'name="rg_emissor"' in response.get_data(as_text=True)

    criado = client.post(
        "/clientes/novo",
        data={
            "nome": "Cliente RG Teste",
            "rg": "12.345.678-9",
            "rg_emissor": "SSP-PI",
        },
    )
    assert criado.status_code == 302
    with app.app_context():
        cliente = Cliente.query.filter_by(nome="Cliente RG Teste").one()
        cliente_id = cliente.id
        assert cliente.rg == "12.345.678-9"
        assert cliente.rg_emissor == "SSP-PI"

    formulario = client.get(f"/clientes/{cliente_id}/editar")
    html = formulario.get_data(as_text=True)
    assert formulario.status_code == 200
    assert 'value="12.345.678-9"' in html
    assert 'value="SSP-PI"' in html

    editado = client.post(
        f"/clientes/{cliente_id}/editar",
        data={
            "nome": "Cliente RG Teste",
            "rg": "98.765.432-1",
            "rg_emissor": "PC-PI",
        },
    )
    assert editado.status_code == 302
    with app.app_context():
        cliente = db.session.get(Cliente, cliente_id)
        assert cliente.rg == "98.765.432-1"
        assert cliente.rg_emissor == "PC-PI"
        db.session.delete(cliente)
        db.session.commit()
