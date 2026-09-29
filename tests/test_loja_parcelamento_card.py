from pathlib import Path

from app.utils.parcelamento import gerar_linhas_parcelas


ROOT = Path(__file__).parents[1]
CARD = ROOT / "app/loja/templates/loja/_card_produto.html"
CARD_ALTERNATIVO = ROOT / "app/loja/templates/loja/_card_produto 2.html"
ROUTES = ROOT / "app/loja/routes.py"


class TaxaTeste:
    def __init__(self, numero_parcelas, juros):
        self.numero_parcelas = numero_parcelas
        self.juros = juros


def test_calculo_de_12x_considera_a_taxa_cadastrada():
    linhas = gerar_linhas_parcelas(1200, [TaxaTeste(12, 10)])
    parcela_12x = next(linha for linha in linhas if linha["rotulo"] == "12x")
    assert parcela_12x["total"] == 1333.3333333333333
    assert parcela_12x["parcela"] == 111.1111111111111


def test_card_usa_o_mesmo_calculo_de_parcelamento_do_detalhe():
    rotas = ROUTES.read_text(encoding="utf-8")
    card = CARD.read_text(encoding="utf-8")
    card_alternativo = CARD_ALTERNATIVO.read_text(encoding="utf-8")
    assert "def inject_parcelamento_helper" in rotas
    assert "gerar_linhas_parcelas(valor_base, taxas)" in rotas
    assert "calcular_parcela_12x(precos.preco_a_vista)" in card
    assert "parcela_12x_card.parcela" in card
    assert "calcular_parcela_12x(precos.preco_a_vista)" in card_alternativo
    assert "precos.preco_a_vista / 12" not in card
    assert "precos.preco_a_vista / 12" not in card_alternativo
