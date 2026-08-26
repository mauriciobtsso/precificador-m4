from flask import Flask

from app.loja.routes import (
    _limpar_foto_para_fallback,
    gerar_analise_local,
    normalizar_foto_loja,
    normalizar_markdown_analise,
)


def _app():
    app = Flask(__name__)
    app.config["SERVER_NAME"] = "localhost"
    app.secret_key = "test-key"
    return app


def test_normaliza_foto_r2_para_cdn_e_preserva_fallback_original():
    foto = "https://pub-exemplo.r2.dev/m4-loja-publico/produtos/fotos/10/arma.webp#arquivo.webp"

    with _app().app_context():
        assert normalizar_foto_loja(foto) == "https://cdn.m4tatica.com.br/produtos/fotos/10/arma.webp"
        assert _limpar_foto_para_fallback(foto) == "https://pub-exemplo.r2.dev/m4-loja-publico/produtos/fotos/10/arma.webp"


def test_normaliza_foto_vazia_para_placeholder():
    with _app().app_context():
        assert normalizar_foto_loja("").endswith("/static/img/sem-foto.jpg")
        assert _limpar_foto_para_fallback("produtos/fotos/10/arma.webp") == ""


def test_parecer_local_tem_estrutura_markdown_comparativa():
    produtos = [
        {
            "nome": "Produto A",
            "categoria": "Fuzil",
            "calibre": ".300 BLK",
            "preco_vista": 10000,
            "especificacoes": {
                "marca": "Marca A",
                "tipo": "Arma de Fogo",
                "funcionamento": "Semiautomático",
                "peso": "3 kg",
                "comprimento": "70 cm",
            },
        },
        {
            "nome": "Produto B",
            "categoria": "Fuzil",
            "calibre": ".300 BLK",
            "preco_vista": 12000,
            "especificacoes": {
                "marca": "Marca B",
                "tipo": "Arma de Fogo",
                "funcionamento": "Semiautomático",
                "peso": "3,5 kg",
                "comprimento": "75 cm",
            },
        },
    ]

    parecer = gerar_analise_local(produtos)

    assert "# Análise comparativa técnica" in parecer
    assert "## Comparação objetiva" in parecer
    assert "| Armamento | Fabricante | Calibre | Tipo | Preço à vista |" in parecer
    assert "R$ 10.000,00" in parecer
    assert "Não informado" not in parecer


def test_normaliza_resposta_markdown_cercada_em_codigo():
    resposta = "```markdown\n## Parecer técnico\n\nConteúdo.\n```"
    assert normalizar_markdown_analise(resposta) == "## Parecer técnico\n\nConteúdo."
    assert normalizar_markdown_analise("Texto sem título").startswith("## Parecer técnico")
