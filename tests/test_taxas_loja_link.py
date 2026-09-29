from pathlib import Path

from app import db
from app.loja.models_admin import TaxaLojaLink
from app.models import Taxa

ROOT = Path(__file__).parents[1]


def test_taxas_da_loja_nao_alteram_taxas_dos_fluxos_internos(client, app):
    from app.loja.routes import _taxas_loja_cache_version

    lista = client.get("/admin-loja/taxas-link")
    formulario = client.get("/admin-loja/taxas-link/novo")
    assert lista.status_code == 200
    assert "Taxas de parcelamento da loja" in lista.get_data(as_text=True)
    assert formulario.status_code == 200
    assert 'name="numero_parcelas"' in formulario.get_data(as_text=True)

    with app.app_context():
        db.session.query(TaxaLojaLink).filter_by(numero_parcelas=35).delete()
        interna = Taxa.query.filter_by(numero_parcelas=35).first()
        interna_criada = interna is None
        if interna is None:
            interna = Taxa(numero_parcelas=35, juros=2.5)
            db.session.add(interna)
            juros_interno_anterior = None
        else:
            juros_interno_anterior = interna.juros
            interna.juros = 2.5
        db.session.commit()
        taxa_interna_id = interna.id
        versao_antes = _taxas_loja_cache_version()

    response = client.post(
        "/admin-loja/taxas-link/novo",
        data={"numero_parcelas": "35", "juros": "9,75"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Taxa da loja criada com sucesso" in response.get_data(as_text=True)

    with app.app_context():
        taxa_loja = TaxaLojaLink.query.filter_by(numero_parcelas=35).one()
        taxa_interna = db.session.get(Taxa, taxa_interna_id)
        assert taxa_loja.juros == 9.75
        assert taxa_interna.juros == 2.5
        versao_depois = _taxas_loja_cache_version()
        assert versao_depois != versao_antes

    response = client.post(
        f"/admin-loja/taxas-link/editar/{taxa_loja.id}",
        data={"numero_parcelas": "34", "juros": "10"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        editada = db.session.get(TaxaLojaLink, taxa_loja.id)
        assert editada.numero_parcelas == 34
        assert editada.juros == 10.0
        assert db.session.get(Taxa, taxa_interna_id).juros == 2.5

    response = client.post(
        f"/admin-loja/taxas-link/excluir/{taxa_loja.id}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(TaxaLojaLink, taxa_loja.id) is None
        assert db.session.get(Taxa, taxa_interna_id).juros == 2.5
        if interna_criada:
            db.session.delete(db.session.get(Taxa, taxa_interna_id))
        else:
            db.session.get(Taxa, taxa_interna_id).juros = juros_interno_anterior
        db.session.commit()


def test_calculo_dos_cards_usa_a_tabela_exclusiva_da_loja(app):
    from app.loja.routes import inject_parcelamento_helper

    with app.app_context():
        anterior = TaxaLojaLink.query.filter_by(numero_parcelas=12).first()
        if anterior:
            juros_anterior = anterior.juros
            anterior.juros = 10
            taxa_loja = anterior
        else:
            juros_anterior = None
            taxa_loja = TaxaLojaLink(numero_parcelas=12, juros=10)
            db.session.add(taxa_loja)
        db.session.commit()
        try:
            calcular_parcela_12x = inject_parcelamento_helper()["calcular_parcela_12x"]
            parcela = calcular_parcela_12x(1200)
            assert parcela["total"] == 1333.3333333333333
            assert parcela["parcela"] == 111.1111111111111
        finally:
            if anterior:
                anterior.juros = juros_anterior
            else:
                db.session.delete(taxa_loja)
            db.session.commit()


def test_vitrine_detalhe_e_modal_usam_opcoes_calculadas_com_taxas_da_loja():
    rotas = (ROOT / "app/loja/routes.py").read_text(encoding="utf-8")
    card = (ROOT / "app/loja/templates/loja/_card_produto.html").read_text(encoding="utf-8")
    detalhe = (ROOT / "app/loja/templates/loja/produto_detalhe.html").read_text(encoding="utf-8")

    assert "TaxaLojaLink.query.order_by(TaxaLojaLink.numero_parcelas)" in rotas
    assert "calcular_parcela_12x(precos.preco_a_vista)" in card
    assert "parcela_12x_card.parcela" in card
    assert "opcoes_parcelamento_loja_v1_" in rotas
    assert "for item in opcoes_parcelamento" in detalhe
    assert "opcoes_parcelamento=opcoes_parcelamento" in rotas


def test_rotas_publicas_de_precos_incluem_versao_de_cache_das_taxas(app):
    from app.loja.routes import _categoria_cache_key, _detalhe_produto_cache_key, _index_cache_key, invalidar_cache_taxas_loja

    with app.app_context():
        with app.test_request_context("/loja/categoria/teste"):
            chave_categoria_antes = _categoria_cache_key()
            chave_detalhe_antes = _detalhe_produto_cache_key()
        with app.test_request_context("/loja/"):
            chave_index_antes = _index_cache_key()

        invalidar_cache_taxas_loja()
        db.session.commit()

        with app.test_request_context("/loja/categoria/teste"):
            assert _categoria_cache_key() != chave_categoria_antes
            assert _detalhe_produto_cache_key() != chave_detalhe_antes
        with app.test_request_context("/loja/"):
            assert _index_cache_key() != chave_index_antes


def test_formularios_de_taxas_link_incluem_csrf_e_exclusividade():
    lista = (ROOT / "app/loja_admin/templates/loja_admin/taxas_link/lista.html").read_text(encoding="utf-8")
    formulario = (ROOT / "app/loja_admin/templates/loja_admin/taxas_link/form.html").read_text(encoding="utf-8")
    rotas_admin = (ROOT / "app/loja_admin/routes.py").read_text(encoding="utf-8")

    assert 'name="csrf_token"' in lista
    assert 'name="csrf_token"' in formulario
    assert "@login_required\ndef taxas_link" in rotas_admin
    assert "TaxaLojaLink" in rotas_admin
    assert "Taxa.query" not in rotas_admin[rotas_admin.index("# TAXAS DE PARCELAMENTO EXCLUSIVAS DA LOJA"):]
