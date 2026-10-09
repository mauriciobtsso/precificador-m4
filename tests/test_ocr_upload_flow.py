from io import BytesIO
from pathlib import Path

from app.services import ocr_local, ocr_pipeline
from app.uploads import routes as upload_routes


CLIENTE_ID = 7654321
CAMINHO_R2 = f"clientes/{CLIENTE_ID}/documentos/arquivo-sintetico.pdf"


def _enviar_pdf(client):
    with client.session_transaction() as sessao:
        sessao["loja_cliente_id"] = CLIENTE_ID
    return client.post(
        f"/uploads/{CLIENTE_ID}/documento",
        data={"arquivo": (BytesIO(b"%PDF-1.7\nconteudo sintetico"), "arquivo.pdf")},
        content_type="multipart/form-data",
    )


def test_upload_guarda_arquivo_e_abre_cadastro_manual_quando_ocr_nao_le(monkeypatch, client):
    armazenados = []
    monkeypatch.setattr(
        upload_routes,
        "_upload_to_r2",
        lambda arquivo, cliente_id, subpasta: armazenados.append((cliente_id, subpasta)) or CAMINHO_R2,
    )
    monkeypatch.setattr(
        ocr_pipeline,
        "processar_documento",
        lambda *_args: {"erro": "API de OCR indisponível", "ocr_engine": "ocr.space"},
    )

    resposta = _enviar_pdf(client)
    payload = resposta.get_json()

    assert resposta.status_code == 200
    assert armazenados == [(CLIENTE_ID, "documentos")]
    assert payload["dados"] == {}
    assert payload["caminho_arquivo"] == CAMINHO_R2
    assert "Preencha os campos manualmente" in payload["ocr_warning"]
    assert "API de OCR indisponível" not in resposta.get_data(as_text=True)
    assert "traceback" not in payload


def test_upload_preserva_campos_quando_ocr_tem_sucesso(monkeypatch, client):
    monkeypatch.setattr(upload_routes, "_upload_to_r2", lambda *_args: CAMINHO_R2)
    resultado = {
        "ocr_engine": "local",
        "ia_engine": "teste",
        "resultado": {"categoria": "CNH", "numero_documento": "TESTE-123"},
    }
    monkeypatch.setattr(ocr_pipeline, "processar_documento", lambda *_args: resultado)

    resposta = _enviar_pdf(client)
    payload = resposta.get_json()

    assert resposta.status_code == 200
    assert payload["caminho_arquivo"] == CAMINHO_R2
    assert payload["dados"]["resultado"]["categoria"] == "CNH"
    assert "ocr_warning" not in payload


def test_upload_js_envia_csrf_sem_registrar_payloads_pessoais():
    fonte = Path("app/static/js/documentos.js").read_text(encoding="utf-8")

    assert 'headers: { "X-CSRFToken": csrfToken }' in fonte
    assert 'formData.append("csrf_token", csrfToken)' in fonte
    assert "Retorno bruto" not in fonte
    assert "Normalizado para preenchimento" not in fonte
    assert 'toast.querySelector(".toast-body").textContent = mensagem' in fonte


def test_ocr_local_aplica_caminho_do_tesseract_configurado(app, monkeypatch):
    engine = ocr_local.pytesseract.pytesseract
    monkeypatch.setattr(engine, "tesseract_cmd", "antes")
    app.config["TESSERACT_CMD"] = "/usr/local/bin/tesseract-test"

    with app.app_context():
        ocr_local._configure_tesseract()

    assert engine.tesseract_cmd == "/usr/local/bin/tesseract-test"
