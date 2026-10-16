from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pdfminer.high_level import extract_pages, extract_text

from app import db
from app.clientes.models import Cliente
from app.certidoes.declaracoes import MODELOS_PADRAO, gerar_declaracao
# Cliente possui um relacionamento com este modelo, que precisa estar registrado.
from app.estoque.models import ItemEstoque as _ItemEstoque


def _cliente_teste():
    endereco = SimpleNamespace(
        tipo="residencial",
        logradouro="Rua de Teste",
        numero="42",
        complemento="Casa 2",
        bairro="Centro",
        cidade="Teresina",
        estado="PI",
        cep="64000-000",
    )
    return SimpleNamespace(
        id=123,
        nome="Cliente de Teste",
        documento="123.456.789-00",
        enderecos=[endereco],
    )


def test_declaracao_residencia_inclui_proprietario_vinculo_e_data():
    dados = {
        "proprietario_nome": "Proprietária de Teste",
        "proprietario_documento": "987.654.321-00",
        "proprietario_rg": "1234567",
        "proprietario_rg_emissor": "SSP-PI",
        "proprietario_endereco": "Av. Exemplo, 100, Centro, Teresina/PI",
        "vinculo": "mãe",
        "local": "Teresina/PI",
    }

    pdf = gerar_declaracao(_cliente_teste(), "residencia", dados, date(2026, 6, 1))
    texto = " ".join(extract_text(BytesIO(pdf)).split())

    assert len(list(extract_pages(BytesIO(pdf)))) == 1
    assert "DECLARAÇÃO DE RESIDÊNCIA" in texto
    assert "Proprietária de Teste" in texto
    assert "987.654.321-00" in texto
    assert "1234567" in texto
    assert "SSP-PI" in texto
    assert "Cliente de Teste" in texto
    assert "Av. Exemplo, 100, Centro, Teresina/PI" in texto
    assert "mãe" in texto
    assert "Teresina/PI, 1º de Junho de 2026" in texto


def test_declaracao_nao_inquerito_inclui_endereco_e_texto_do_modelo():
    pdf = gerar_declaracao(_cliente_teste(), "nao_inquerito", data_emissao=date(2026, 6, 15))
    texto = " ".join(extract_text(BytesIO(pdf)).split())

    assert len(list(extract_pages(BytesIO(pdf)))) == 1
    assert "INQUÉRITOS POLICIAIS OU PROCESSOS CRIMINAIS" in texto
    assert "Cliente de Teste" in texto
    assert "123.456.789-00" in texto
    assert "Rua de Teste" in texto
    assert "Teresina/PI, 15 de Junho de 2026" in texto
    assert "Art. 299" in texto


def test_formulario_residencia_exige_dados_do_declarante_e_gera_pdf(client, app):
    documento = f"TEST{uuid4().hex[:12]}"
    with app.app_context():
        cliente = Cliente(nome="Cliente Rota Teste", documento=documento)
        db.session.add(cliente)
        db.session.commit()
        cliente_id = cliente.id

    try:
        url = f"/certidoes/cliente/{cliente_id}/declaracao/residencia"
        resposta = client.get(url)
        assert resposta.status_code == 200
        assert "Dados da pessoa proprietária/declarante" in resposta.get_data(as_text=True)

        incompleta = client.post(url, data={})
        assert incompleta.status_code == 400

        completa = client.post(
            url,
            data={
                "proprietario_nome": "Declarante Rota Teste",
                "proprietario_documento": "98765432100",
                "proprietario_rg": "12345",
                "proprietario_rg_emissor": "SSP-PI",
                "proprietario_endereco": "Rua Exemplo, 10, Teresina/PI",
                "vinculo": "mãe",
                "local": "Teresina/PI",
            },
        )
        assert completa.status_code == 200
        assert completa.mimetype == "application/pdf"
        assert completa.data.startswith(b"%PDF")
        assert "declaracao_residencia_" in completa.headers["Content-Disposition"]
    finally:
        with app.app_context():
            cliente = db.session.get(Cliente, cliente_id)
            if cliente:
                db.session.delete(cliente)
                db.session.commit()


def test_migracao_atualiza_apenas_modelos_que_nao_foram_personalizados():
    caminho = Path(__file__).parents[1] / "migrations" / "versions" / "20261016_update_declaracoes.py"
    spec = spec_from_file_location("migration_update_declaracoes", caminho)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert {chave: (titulo, conteudo) for titulo, chave, conteudo in MODELOS_PADRAO} == migration._NOVOS

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE modelos_documento ("
            "id INTEGER PRIMARY KEY, titulo VARCHAR(100) NOT NULL, "
            "chave VARCHAR(50) NOT NULL UNIQUE, conteudo TEXT NOT NULL)"
        ))
        connection.execute(
            sa.text("INSERT INTO modelos_documento (id, titulo, chave, conteudo) VALUES (1, :titulo, :chave, :conteudo)"),
            {
                "titulo": "Declaração de Residência",
                "chave": "declaracao_residencia",
                "conteudo": migration._ANTIGOS["declaracao_residencia"],
            },
        )
        connection.execute(
            sa.text("INSERT INTO modelos_documento (id, titulo, chave, conteudo) VALUES (2, :titulo, :chave, :conteudo)"),
            {
                "titulo": "Meu modelo personalizado",
                "chave": "declaracao_nao_inquerito",
                "conteudo": migration._ANTIGOS["declaracao_nao_inquerito"],
            },
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        conteudos = dict(connection.execute(sa.text("SELECT chave, conteudo FROM modelos_documento")).all())
        assert "{{ proprietario.nome }}" in conteudos["declaracao_residencia"]
        assert "Art. 299" in conteudos["declaracao_nao_inquerito"]
        titulo_customizado = connection.execute(
            sa.text("SELECT titulo FROM modelos_documento WHERE chave = 'declaracao_nao_inquerito'")
        ).scalar_one()
        assert titulo_customizado == "Meu modelo personalizado"

        connection.execute(
            sa.text("UPDATE modelos_documento SET conteudo = :conteudo WHERE chave = 'declaracao_nao_inquerito'"),
            {"conteudo": "Texto que a equipe já personalizou."},
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()

        conteudos = dict(connection.execute(sa.text("SELECT chave, conteudo FROM modelos_documento")).all())
        assert conteudos["declaracao_residencia"] == migration._ANTIGOS["declaracao_residencia"]
        assert conteudos["declaracao_nao_inquerito"] == "Texto que a equipe já personalizou."
        titulo_customizado = connection.execute(
            sa.text("SELECT titulo FROM modelos_documento WHERE chave = 'declaracao_nao_inquerito'")
        ).scalar_one()
        assert titulo_customizado == "Meu modelo personalizado"

    engine.dispose()
