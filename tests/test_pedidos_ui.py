from pathlib import Path
from types import SimpleNamespace

from app.pedidos.routes import _cliente_eh_cnpj
from app.utils.gerar_pedidos import gerar_pedido_m4


def test_fornecedor_com_cnpj_formatado_eh_aceito():
    assert _cliente_eh_cnpj(SimpleNamespace(documento="41.654.218/0001-47"))
    assert _cliente_eh_cnpj(SimpleNamespace(documento="41654218000147"))
    assert not _cliente_eh_cnpj(SimpleNamespace(documento="123.456.789-09"))
    assert not _cliente_eh_cnpj(SimpleNamespace(documento=None))


def test_gerador_pdf_cria_documento_comercial_no_caminho_informado(tmp_path):
    destino = tmp_path / "pedido-teste.pdf"
    caminho = gerar_pedido_m4(
        itens=[("SKU-01", "Rifle de teste", 2, 1000.0)],
        cond_pagto="30 dias",
        perc_armas=-5,
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
