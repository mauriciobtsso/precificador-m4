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
from app.clientes.models import Cliente, DadosDeclaracaoResidencia
from app.certidoes.declaracoes import MODELOS_PADRAO, gerar_declaracao
from app.models import ModeloDocumento
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
        documento="12345678900",
        enderecos=[endereco],
    )


def test_declaracao_residencia_inclui_proprietario_vinculo_e_data():
    dados = {
        "proprietario_nome": "Proprietária de Teste",
        "proprietario_documento": "98765432100",
        "proprietario_rg": "1234567",
        "proprietario_rg_emissor": "SSP-PI",
        "proprietario_endereco": "Rua do Declarante, 10, Centro, Teresina/PI",
        "cliente_endereco": "Av. do Cliente, 999, Bairro Novo, Teresina/PI",
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
    assert "Rua do Declarante, 10, Centro, Teresina/PI" in texto
    assert "Av. do Cliente, 999, Bairro Novo, Teresina/PI" in texto
    assert "endereço acima citado" not in texto
    assert "titular do imóvel" not in texto
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
        assert "Dados da pessoa declarante" in resposta.get_data(as_text=True)
        assert 'name="cliente_endereco"' in resposta.get_data(as_text=True)

        incompleta = client.post(url, data={})
        assert incompleta.status_code == 400
        with app.app_context():
            assert DadosDeclaracaoResidencia.query.filter_by(cliente_id=cliente_id).first() is None

        completa = client.post(
            url,
            data={
                "proprietario_nome": "Declarante Rota Teste",
                "proprietario_documento": "98765432100",
                "proprietario_rg": "12345",
                "proprietario_rg_emissor": "SSP-PI",
                "proprietario_endereco": "Rua do Declarante, 10, Teresina/PI",
                "cliente_endereco": "Av. do Cliente, 999, Teresina/PI",
                "vinculo": "mãe",
                "local": "Teresina/PI",
            },
        )
        assert completa.status_code == 200
        assert completa.mimetype == "application/pdf"
        assert completa.data.startswith(b"%PDF")
        assert "declaracao_residencia_" in completa.headers["Content-Disposition"]
        texto_pdf = " ".join(extract_text(BytesIO(completa.data)).split())
        assert "987.654.321-00" in texto_pdf
        assert "Rua do Declarante, 10, Teresina/PI" in texto_pdf
        assert "Av. do Cliente, 999, Teresina/PI" in texto_pdf

        with app.app_context():
            salvo = DadosDeclaracaoResidencia.query.filter_by(cliente_id=cliente_id).one()
            assert salvo.proprietario_nome == "Declarante Rota Teste"
            assert salvo.proprietario_rg == "12345"
            assert salvo.proprietario_endereco == "Rua do Declarante, 10, Teresina/PI"
            assert salvo.cliente_endereco == "Av. do Cliente, 999, Teresina/PI"
            assert salvo.vinculo == "mãe"

        reaberta = client.get(url)
        html = reaberta.get_data(as_text=True)
        assert reaberta.status_code == 200
        assert "Os dados da última declaração deste cliente foram carregados" in html
        assert 'value="Declarante Rota Teste"' in html
        assert 'value="12345"' in html
        assert "Rua do Declarante, 10, Teresina/PI</textarea>" in html
        assert "Av. do Cliente, 999, Teresina/PI</textarea>" in html
    finally:
        with app.app_context():
            cliente = db.session.get(Cliente, cliente_id)
            if cliente:
                db.session.delete(cliente)
                db.session.commit()


def test_texto_personalizado_no_painel_e_usado_no_pdf(app):
    with app.app_context():
        modelo = ModeloDocumento.query.filter_by(chave="declaracao_residencia").first()
        modelo_novo = modelo is None
        if modelo_novo:
            modelo = ModeloDocumento(
                titulo="Modelo editado no teste",
                chave="declaracao_residencia",
                conteudo="Texto editado: <b>{{ proprietario.nome }}</b>; {{ declaracao.vinculo }}; {{ cliente.nome }}.",
            )
            db.session.add(modelo)
        else:
            titulo_anterior, conteudo_anterior = modelo.titulo, modelo.conteudo
            modelo.titulo = "Modelo editado no teste"
            modelo.conteudo = "Texto editado: <b>{{ proprietario.nome }}</b>; {{ declaracao.vinculo }}; {{ cliente.nome }}."
        db.session.commit()

        try:
            pdf = gerar_declaracao(
                _cliente_teste(),
                "residencia",
                {
                    "proprietario_nome": "Dona da Casa",
                    "proprietario_documento": "98765432100",
                    "proprietario_rg": "1234",
                    "proprietario_rg_emissor": "SSP-PI",
                    "proprietario_endereco": "Rua de Teste, 42",
                    "vinculo": "mãe",
                    "local": "Teresina/PI",
                },
                date(2026, 6, 1),
            )
            texto = " ".join(extract_text(BytesIO(pdf)).split())
            assert "MODELO EDITADO NO TESTE" in texto
            assert "Texto editado: Dona da Casa; mãe; Cliente de Teste." in texto
        finally:
            if modelo_novo:
                db.session.delete(modelo)
            else:
                modelo.titulo = titulo_anterior
                modelo.conteudo = conteudo_anterior
            db.session.commit()


def test_migracao_atualiza_apenas_modelos_que_nao_foram_personalizados():
    caminho = Path(__file__).parents[1] / "migrations" / "versions" / "20261016_update_declaracoes.py"
    spec = spec_from_file_location("migration_update_declaracoes", caminho)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
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


def test_migracao_enderecos_separados_preserva_texto_personalizado():
    caminho = Path(__file__).parents[1] / "migrations" / "versions" / "20261016_sep_end_res.py"
    spec = spec_from_file_location("migration_sep_enderecos_residencia", caminho)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert len(migration.revision) <= 32
    modelos_residencia = {
        chave: (titulo, conteudo)
        for titulo, chave, conteudo in MODELOS_PADRAO
        if chave == "declaracao_residencia"
    }
    assert modelos_residencia == {migration._CHAVE: ("Declaração de Residência", migration._NOVO)}

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
                "titulo": "Declaração personalizada",
                "chave": migration._CHAVE,
                "conteudo": migration._ANTIGO,
            },
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        conteudo = connection.execute(
            sa.text("SELECT conteudo FROM modelos_documento WHERE chave = :chave"),
            {"chave": migration._CHAVE},
        ).scalar_one()
        assert conteudo == migration._NOVO
        assert "{{ proprietario.endereco_completo }}" in conteudo
        assert "{{ cliente.endereco_completo }}" in conteudo

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        conteudo = connection.execute(
            sa.text("SELECT conteudo FROM modelos_documento WHERE chave = :chave"),
            {"chave": migration._CHAVE},
        ).scalar_one()
        assert conteudo == migration._ANTIGO

        texto_customizado = "Texto personalizado pela equipe."
        connection.execute(
            sa.text("UPDATE modelos_documento SET conteudo = :conteudo WHERE chave = :chave"),
            {"conteudo": texto_customizado, "chave": migration._CHAVE},
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        conteudo = connection.execute(
            sa.text("SELECT conteudo FROM modelos_documento WHERE chave = :chave"),
            {"chave": migration._CHAVE},
        ).scalar_one()
        assert conteudo == texto_customizado

    engine.dispose()


def test_migracao_cria_tabela_unica_de_dados_da_declaracao():
    caminho = Path(__file__).parents[1] / "migrations" / "versions" / "20261016_decl_res_data.py"
    spec = spec_from_file_location("migration_decl_res_data", caminho)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert len(migration.revision) <= 32
    assert migration.down_revision == "20261016_sep_end_res"

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE clientes (id INTEGER PRIMARY KEY)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        inspector = sa.inspect(connection)
        assert inspector.has_table("clientes_declaracoes_residencia")
        columns = {column["name"] for column in inspector.get_columns("clientes_declaracoes_residencia")}
        assert {
            "cliente_id",
            "proprietario_nome",
            "proprietario_documento",
            "proprietario_rg",
            "proprietario_endereco",
            "cliente_endereco",
            "vinculo",
            "local",
        }.issubset(columns)
        unique = inspector.get_unique_constraints("clientes_declaracoes_residencia")
        assert any(constraint["column_names"] == ["cliente_id"] for constraint in unique)

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert not sa.inspect(connection).has_table("clientes_declaracoes_residencia")

    engine.dispose()
