from pathlib import Path
from types import SimpleNamespace

from app.pedidos.routes import _cliente_eh_cnpj
from app.utils.gerar_pedidos import format_brl, gerar_pedido_m4


TEMPLATE = Path(__file__).parents[1] / "app/templates/pedidos/novo.html"


def test_fornecedor_com_cnpj_formatado_eh_aceito():
    assert _cliente_eh_cnpj(SimpleNamespace(documento="41.654.218/0001-47"))
    assert _cliente_eh_cnpj(SimpleNamespace(documento="41654218000147"))
    assert not _cliente_eh_cnpj(SimpleNamespace(documento="123.456.789-09"))
    assert not _cliente_eh_cnpj(SimpleNamespace(documento=None))


def test_formulario_de_valores_usa_quatro_casas_decimais():
    conteudo = TEMPLATE.read_text(encoding="utf-8")

    assert "('%.4f' % (item.valor_unitario or 0))" in conteudo
    assert "scale:4" in conteudo
    assert "minimumFractionDigits:4" in conteudo
    assert "maximumFractionDigits:4" in conteudo


def test_formatacao_monetaria_preserva_quatro_casas():
    assert format_brl(1.1111) == "R$ 1,1111"


def test_pdf_usa_linguagem_de_solicitacao_de_compra():
    conteudo = (Path(__file__).parents[1] / "app/utils/gerar_pedidos.py").read_text(encoding="utf-8")

    assert "ENDEREÇO E CONTATO DO FORNECEDOR" in conteudo
    assert "Solicitação de compra emitida pela M4 Tática" in conteudo
    assert "CONTATO E ENTREGA" not in conteudo
    assert "Não substitui nota fiscal" not in conteudo


def test_gerador_pdf_cria_documento_comercial_no_caminho_informado(tmp_path):
    destino = tmp_path / "pedido-teste.pdf"
    caminho = gerar_pedido_m4(
        itens=[("SKU-01", "Rifle de teste", 2, 1.1111)],
        cond_pagto="30 dias",
        perc_armas=0,
        perc_municoes=-3,
        modo="por_tipo",
        numero_pedido="20260001",
        data_pedido="27/08/2026",
        fornecedor_nome="Fornecedor Teste LTDA",
        fornecedor_cnpj="41.654.218/0001-47",
        fornecedor_endereco="Rua Teste, 10 - Teresina/PI",
        fornecedor_cr="CR 12345",
        fornecedor_contato="(86) 99999-0000",
        output_path=destino,
    )

    assert Path(caminho) == destino
    assert destino.exists()
    assert destino.read_bytes().startswith(b"%PDF")
    assert destino.stat().st_size > 2000
