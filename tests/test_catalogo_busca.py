from decimal import Decimal
from uuid import uuid4

from app import db
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import CalibreProduto
from app.produtos.models import Produto


def _criar_produtos_de_teste():
    tag = uuid4().hex[:10]
    categoria = CategoriaProduto(nome=f"Pistolas Busca {tag}")
    calibre_9mm = CalibreProduto(nome=f"9mm {tag}")
    calibre_380 = CalibreProduto(nome=f".380 {tag}")

    produto_9mm = Produto(
        codigo=f"CAT-BUSCA-9MM-{tag}",
        nome=f"Modelo Alfa {tag}",
        nome_comercial=f"Modelo Alfa {tag}",
        slug=f"modelo-alfa-{tag}",
        visivel_loja=True,
        categoria=categoria,
        calibre_rel=calibre_9mm,
        preco_a_vista=Decimal("100.00"),
    )
    produto_380 = Produto(
        codigo=f"CAT-BUSCA-380-{tag}",
        nome=f"Modelo Beta {tag}",
        nome_comercial=f"Modelo Beta {tag}",
        slug=f"modelo-beta-{tag}",
        visivel_loja=True,
        categoria=categoria,
        calibre_rel=calibre_380,
        preco_a_vista=Decimal("200.00"),
    )

    db.session.add_all([produto_9mm, produto_380])
    db.session.commit()
    return tag, calibre_9mm, produto_9mm, produto_380


def test_busca_com_varios_termos_encontra_categoria_e_calibre(client):
    tag, _, produto_9mm, produto_380 = _criar_produtos_de_teste()

    resposta = client.get(
        "/catalogo/",
        query_string={"q": f"Busca {tag} 9mm"},
    )

    assert resposta.status_code == 200
    pagina = resposta.get_data(as_text=True)
    assert produto_9mm.slug in pagina
    assert produto_9mm.nome_comercial in pagina
    assert produto_380.slug not in pagina
    assert "1 produto" in pagina


def test_filtro_por_calibre_limita_os_resultados(client):
    _, calibre_9mm, produto_9mm, produto_380 = _criar_produtos_de_teste()

    resposta = client.get(
        "/catalogo/",
        query_string={"calibre": calibre_9mm.id},
    )

    assert resposta.status_code == 200
    pagina = resposta.get_data(as_text=True)
    assert produto_9mm.slug in pagina
    assert produto_380.slug not in pagina
    assert f'value="{calibre_9mm.id}" selected' in pagina


def test_busca_por_categoria_pode_ser_combinada_com_calibre(client):
    tag, calibre_9mm, produto_9mm, produto_380 = _criar_produtos_de_teste()

    resposta = client.get(
        "/catalogo/",
        query_string={"q": f"Busca {tag}", "calibre": calibre_9mm.id},
    )

    assert resposta.status_code == 200
    pagina = resposta.get_data(as_text=True)
    assert produto_9mm.slug in pagina
    assert produto_380.slug not in pagina
    assert f'name="q" value="Busca {tag}"' in pagina


def test_api_de_sugestoes_busca_todos_os_termos(client):
    tag, _, produto_9mm, produto_380 = _criar_produtos_de_teste()

    resposta = client.get(
        "/catalogo/api/buscar",
        query_string={"q": f"Busca {tag} 9mm"},
    )

    assert resposta.status_code == 200
    slugs = [produto["slug"] for produto in resposta.get_json()["produtos"]]
    assert produto_9mm.slug in slugs
    assert produto_380.slug not in slugs


def test_buscas_principais_sao_formularios_get_sem_transferir_foco(client):
    resposta = client.get("/catalogo/")

    assert resposta.status_code == 200
    pagina = resposta.get_data(as_text=True)
    assert 'id="catHeroSearch"' in pagina
    assert 'id="catSearchInput"' in pagina
    assert 'name="q"' in pagina
    assert 'method="get"' in pagina
    assert "headInput.focus()" not in pagina
    assert "Filtrar por calibre" in pagina
