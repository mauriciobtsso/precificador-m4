from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.produtos.models import Produto
from app.utils.datetime import TZ_FORTALEZA
from app.utils.parsing import parse_decimal, parse_form_datetime


def test_parse_decimal_brasileiro_com_milhar():
    assert parse_decimal("R$ 2.050,00") == Decimal("2050.00")


def test_parse_form_datetime_interpreta_horario_local():
    valor = parse_form_datetime("2026-09-20T10:00")
    assert valor == TZ_FORTALEZA.localize(datetime(2026, 9, 20, 10, 0))


def _produto_com_promocao(inicio, fim):
    return SimpleNamespace(
        codigo="PROMO-TESTE",
        nome="Produto de teste",
        preco_fornecedor=Decimal("100.00"),
        desconto_fornecedor=Decimal("0"),
        frete=Decimal("0"),
        margem=Decimal("0"),
        ipi=Decimal("0"),
        ipi_tipo="%",
        difal=Decimal("0"),
        imposto_venda=Decimal("0"),
        preco_final=Decimal("0"),
        lucro_alvo=Decimal("0"),
        promo_ativada=True,
        promo_preco_fornecedor=Decimal("50.00"),
        promo_data_inicio=inicio,
        promo_data_fim=fim,
    )


def test_promocao_aplica_durante_a_janela(monkeypatch):
    agora = TZ_FORTALEZA.localize(datetime(2026, 9, 20, 10, 0))
    monkeypatch.setattr("app.produtos.models.now_local", lambda: agora)
    produto = _produto_com_promocao(
        TZ_FORTALEZA.localize(datetime(2026, 9, 20, 10, 0)),
        TZ_FORTALEZA.localize(datetime(2026, 9, 25, 10, 0)),
    )

    resultado = Produto.calcular_precos(produto)

    assert resultado["em_oferta"] is True
    assert produto.custo_total == Decimal("50.00")


def test_promocao_encerra_no_instante_final(monkeypatch):
    agora = TZ_FORTALEZA.localize(datetime(2026, 9, 25, 10, 0, 1))
    monkeypatch.setattr("app.produtos.models.now_local", lambda: agora)
    produto = _produto_com_promocao(
        TZ_FORTALEZA.localize(datetime(2026, 9, 20, 10, 0)),
        TZ_FORTALEZA.localize(datetime(2026, 9, 25, 10, 0)),
    )

    resultado = Produto.calcular_precos(produto)

    assert resultado["em_oferta"] is False
    assert produto.custo_total == Decimal("100.00")
