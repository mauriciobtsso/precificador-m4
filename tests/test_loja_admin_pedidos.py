from pathlib import Path


ROOT = Path(__file__).parents[1]
DETAIL = ROOT / "app/loja_admin/templates/loja_admin/pedidos/detalhe.html"
PRINT = ROOT / "app/loja_admin/templates/loja_admin/pedidos/imprimir.html"
LABEL = ROOT / "app/loja_admin/templates/loja_admin/pedidos/etiqueta.html"
ROUTES = ROOT / "app/loja_admin/routes.py"


def test_detalhe_usa_relacao_de_itens_do_modelo_e_exibe_dados_do_produto():
    conteudo = DETAIL.read_text(encoding="utf-8")
    assert "{% for item in pedido.items %}" in conteudo
    assert "item.produto.codigo" in conteudo
    assert "item.quantidade" in conteudo
    assert "item.preco_unitario_historico" in conteudo


def test_detalhe_oferece_impressoes_do_pedido_e_da_etiqueta():
    conteudo = DETAIL.read_text(encoding="utf-8")
    assert "loja_admin.imprimir_pedido" in conteudo
    assert "loja_admin.imprimir_etiqueta_pedido" in conteudo


def test_rotas_e_templates_de_impressao_estao_registrados():
    rotas = ROUTES.read_text(encoding="utf-8")
    assert "def imprimir_pedido" in rotas
    assert "def imprimir_etiqueta_pedido" in rotas
    assert "pedido.items" in PRINT.read_text(encoding="utf-8")
    assert "pedido.cep" in LABEL.read_text(encoding="utf-8")


def test_layout_do_admin_reduz_fonte_e_bloqueia_overflow_horizontal():
    conteudo = (ROOT / "app/loja_admin/templates/loja_admin/base_admin.html").read_text(encoding="utf-8")
    assert "font-size: 0.9rem" in conteudo
    assert "overflow-x: hidden" in conteudo
    assert "main { min-width: 0; }" in conteudo


def test_valores_do_admin_usam_filtro_de_moeda_brasileira():
    lista = (ROOT / "app/loja_admin/templates/loja_admin/pedidos/lista.html").read_text(encoding="utf-8")
    detalhe = DETAIL.read_text(encoding="utf-8")
    imprimir = PRINT.read_text(encoding="utf-8")
    assert "pedido.total_pedido|currency" in lista
    assert "pedido.total_pedido|currency" in detalhe
    assert "item.preco_unitario_historico|currency" in detalhe
    assert "pedido.total_pedido|currency" in imprimir


def test_novo_pedido_quantiza_totais_antes_de_persistir():
    rotas = (ROOT / "app/carrinho/routes.py").read_text(encoding="utf-8")
    assert "from decimal import Decimal, ROUND_HALF_UP" in rotas
    assert "total_pedido = (total_produtos + total_frete).quantize" in rotas
    assert "total_pedido=total_pedido" in rotas
