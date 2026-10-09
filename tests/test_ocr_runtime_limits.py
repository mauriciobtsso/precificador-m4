from types import SimpleNamespace

from PIL import Image

from app.services import ocr_local, ocr_pipeline


def test_ocr_image_sets_timeouts_and_returns_empty_text_on_timeout(monkeypatch):
    chamadas = {}

    def osd_simulado(_imagem, timeout):
        chamadas["osd_timeout"] = timeout
        return "Rotate: 0\n"

    def ocr_simulado(_imagem, *, lang, config, timeout):
        chamadas["ocr_timeout"] = timeout
        raise RuntimeError("timeout sintético")

    monkeypatch.setattr(ocr_local.pytesseract, "image_to_osd", osd_simulado)
    monkeypatch.setattr(ocr_local.pytesseract, "image_to_string", ocr_simulado)
    monkeypatch.setattr(ocr_local, "_preprocess_image", lambda imagem: imagem)

    texto, confianca = ocr_local._ocr_image(Image.new("RGB", (32, 32)))

    assert chamadas == {"osd_timeout": 5, "ocr_timeout": 15}
    assert texto == ""
    assert confianca is None


def test_pdf_text_layer_reads_only_the_page_limit(monkeypatch):
    class PaginaSintetica:
        @staticmethod
        def extract_text(**_kwargs):
            return "texto sintético desta página"

    class PdfSintetico:
        pages = [PaginaSintetica() for _ in range(5)]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    pdfplumber_simulado = SimpleNamespace(open=lambda _arquivo: PdfSintetico())
    monkeypatch.setattr(ocr_local, "pdfplumber", pdfplumber_simulado)

    textos, truncado = ocr_local._pdf_textlayer_extract(b"pdf sintetico", max_pages=3)

    assert len(textos) == 3
    assert truncado is True


def test_pdf_rasterization_passes_page_and_time_limits(monkeypatch):
    parametros = {}

    def conversao_simulada(_bytes, **kwargs):
        parametros.update(kwargs)
        return []

    monkeypatch.setattr(ocr_local, "convert_from_bytes", conversao_simulada)

    ocr_local._pdf_to_images(
        b"%PDF-1.7",
        dpi=200,
        first_page=1,
        last_page=3,
        timeout=15,
    )

    assert parametros["dpi"] == 200
    assert parametros["first_page"] == 1
    assert parametros["last_page"] == 3
    assert parametros["timeout"] == 15


def test_pipeline_limits_local_ocr_to_200dpi_and_three_pages(monkeypatch):
    parametros = {}

    def ocr_local_simulado(**kwargs):
        parametros.update(kwargs)
        return {
            "texts": ["CNH sintetica de teste"],
            "engine": "local",
            "meta": {"truncated": True},
        }

    monkeypatch.setattr(ocr_pipeline.ocr_local, "extract_text_local", ocr_local_simulado)
    monkeypatch.setattr(
        ocr_pipeline.ocr_inteligente,
        "interpretar_documento",
        lambda _texto: {"categoria": "CNH", "engine": "teste"},
    )

    resultado = ocr_pipeline.processar_documento(b"imagem sintetica", "teste.jpg")

    assert parametros["dpi"] == 200
    assert parametros["max_pages"] == 3
    assert resultado["ocr_engine"] == "local"
    assert resultado["resultado"]["categoria"] == "CNH"
    assert "somente as 3 primeiras páginas" in resultado["ocr_warning"]
