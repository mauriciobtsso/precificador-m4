import importlib.util
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db
from app.loja.models_admin import PerguntaFrequente


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_faq_admin_list_and_dashboard_render_management_links(client):
    response = client.get("/admin-loja/perguntas-frequentes")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Perguntas frequentes" in html
    assert "/admin-loja/perguntas-frequentes/nova" in html

    dashboard = client.get("/admin-loja/")
    dashboard_html = dashboard.get_data(as_text=True)
    assert dashboard.status_code == 200
    assert "Gerenciar FAQs" in dashboard_html


def test_faq_admin_requires_login(app, client):
    login_disabled = app.config.get("LOGIN_DISABLED", False)
    app.config["LOGIN_DISABLED"] = False
    try:
        response = client.get("/admin-loja/perguntas-frequentes")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
    finally:
        app.config["LOGIN_DISABLED"] = login_disabled


def test_faq_admin_create_edit_and_unpublish(app, client):
    token = uuid4().hex[:12]
    question = f"Pergunta editável {token}"
    response = client.post(
        "/admin-loja/perguntas-frequentes/nova",
        data={
            "pergunta": question,
            "resposta": "Resposta inicial.",
            "ordem": "23",
            "publicada": "1",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        faq = PerguntaFrequente.query.filter_by(pergunta=question).one()
        faq_id = faq.id
        assert faq.publicada is True
        assert faq.ordem == 23

    response = client.post(
        f"/admin-loja/perguntas-frequentes/editar/{faq_id}",
        data={
            "pergunta": question,
            "resposta": "Resposta atualizada com link.",
            "link_texto": "Saiba mais",
            "link_url": "https://example.com/ajuda",
            "ordem": "4",
            # A caixa não marcada despublica, sem excluir o registro.
        },
    )
    assert response.status_code == 302

    with app.app_context():
        faq = db.session.get(PerguntaFrequente, faq_id)
        assert faq.resposta == "Resposta atualizada com link."
        assert faq.link_texto == "Saiba mais"
        assert faq.link_url == "https://example.com/ajuda"
        assert faq.ordem == 4
        assert faq.publicada is False

    public_page = client.get("/loja/perguntas-frequentes")
    assert question not in public_page.get_data(as_text=True)

    response = client.post(f"/admin-loja/perguntas-frequentes/excluir/{faq_id}")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(PerguntaFrequente, faq_id) is None


def test_faq_admin_rejects_executable_or_incomplete_links(app, client):
    token = uuid4().hex[:12]
    response = client.post(
        "/admin-loja/perguntas-frequentes/nova",
        data={
            "pergunta": f"Pergunta inválida {token}",
            "resposta": "Resposta de teste.",
            "link_texto": "Link inseguro",
            "link_url": "javascript:alert(1)",
            "ordem": "1",
            "publicada": "1",
        },
    )
    assert response.status_code == 200
    assert "URL" in response.get_data(as_text=True)

    with app.app_context():
        assert PerguntaFrequente.query.filter(PerguntaFrequente.pergunta.contains(token)).count() == 0

    response = client.post(
        "/admin-loja/perguntas-frequentes/nova",
        data={
            "pergunta": f"Pergunta sem URL {token}",
            "resposta": "Resposta de teste.",
            "link_texto": "Texto sem destino",
            "ordem": "1",
        },
    )
    assert response.status_code == 200
    assert "Preencha o texto e a URL" in response.get_data(as_text=True)


def test_public_faq_escapes_answer_html(app, client):
    token = uuid4().hex[:12]
    faq = PerguntaFrequente(
        pergunta=f"Pergunta segura {token}",
        resposta="<script>alert('xss')</script>",
        ordem=9000,
        publicada=True,
    )
    with app.app_context():
        db.session.add(faq)
        db.session.commit()
        faq_id = faq.id

    try:
        response = client.get("/loja/perguntas-frequentes")
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in html
        assert "<script>alert('xss')</script>" not in html
    finally:
        with app.app_context():
            db.session.delete(db.session.get(PerguntaFrequente, faq_id))
            db.session.commit()


def test_faq_migration_creates_table_seeds_current_content_and_downgrades():
    migration_path = next((REPO_ROOT / "migrations" / "versions").glob("20261014_add_editable_faq.py"))
    spec = importlib.util.spec_from_file_location("editable_faq_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        rows = connection.execute(
            sa.text("SELECT pergunta, resposta, link_url, ordem, publicada FROM loja_perguntas_frequentes ORDER BY ordem")
        ).mappings().all()
        assert len(rows) == 9
        assert [row["ordem"] for row in rows] == list(range(1, 10))
        assert rows[0]["pergunta"] == "Preciso de porte para comprar uma arma?"
        assert bool(rows[0]["publicada"]) is True
        assert rows[0]["link_url"].startswith("https://www.gov.br/")
        assert "R$ 1.600,00" in rows[-1]["resposta"]

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert not sa.inspect(connection).has_table("loja_perguntas_frequentes")
