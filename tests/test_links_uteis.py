from app import db
from app.loja.models_admin import LinkUtil


def test_pagina_publica_exibe_apenas_links_ativos_e_oculta_resumo_vazio(client, app):
    with app.app_context():
        db.session.add_all([
            LinkUtil(
                titulo="Acesso público",
                url="https://www.gov.br/",
                resumo=None,
                ativo=True,
                ordem=1,
            ),
            LinkUtil(
                titulo="Link oculto",
                url="https://intranet.example/",
                resumo="Não deve aparecer",
                ativo=False,
                ordem=2,
            ),
        ])
        db.session.commit()

    response = client.get("/loja/links-uteis")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Acesso público" in html
    assert "Link oculto" not in html
    assert "None" not in html
    assert "links-uteis-grid" in html


def test_rodape_da_loja_tem_acesso_discreto_a_links_uteis(client):
    response = client.get("/loja/")

    assert response.status_code == 200
    assert 'href="/loja/links-uteis"' in response.get_data(as_text=True)
