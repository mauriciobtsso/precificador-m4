from io import BytesIO
from pathlib import Path

from app.services import ocr_inteligente, ocr_local, ocr_pipeline
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


def test_upload_propaga_aviso_de_documento_parcial(monkeypatch, client):
    aviso = "O OCR analisou somente as 3 primeiras páginas. Confira o restante."
    monkeypatch.setattr(upload_routes, "_upload_to_r2", lambda *_args: CAMINHO_R2)
    monkeypatch.setattr(
        ocr_pipeline,
        "processar_documento",
        lambda *_args: {
            "ocr_engine": "local",
            "engine": "teste",
            "resultado": {"categoria": "CNH"},
            "ocr_warning": aviso,
        },
    )

    resposta = _enviar_pdf(client)

    assert resposta.status_code == 200
    assert resposta.get_json()["ocr_warning"] == aviso


def test_upload_js_envia_csrf_sem_registrar_payloads_pessoais():
    fonte = Path("app/static/js/documentos.js").read_text(encoding="utf-8")

    assert 'headers: { "X-CSRFToken": csrfToken }' in fonte
    assert 'formData.append("csrf_token", csrfToken)' in fonte
    assert "Retorno bruto" not in fonte
    assert "Normalizado para preenchimento" not in fonte
    assert 'toast.querySelector(".toast-body").textContent = mensagem' in fonte


def test_modelo_groq_substitui_modelo_descontinuado():
    assert ocr_inteligente._resolve_groq_model(None) == "openai/gpt-oss-20b"
    assert (
        ocr_inteligente._resolve_groq_model("llama-3.1-8b-instant")
        == "openai/gpt-oss-20b"
    )
    assert (
        ocr_inteligente._resolve_groq_model("qwen/qwen3.8-27b")
        == "qwen/qwen3.8-27b"
    )


def test_interpretacao_ocr_envia_modelo_atual_sem_chamada_externa(monkeypatch):
    chamada = {}

    class RespostaSimulada:
        status_code = 200

        @staticmethod
        def json():
            return {
                "choices": [{
                    "message": {
                        "content": '{"categoria":"CNH","numero_documento":"12345678901"}'
                    }
                }]
            }

    def post_simulado(url, **kwargs):
        chamada["url"] = url
        chamada["payload"] = kwargs["json"]
        return RespostaSimulada()

    monkeypatch.setattr(ocr_inteligente, "GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(ocr_inteligente.requests, "post", post_simulado)

    resultado = ocr_inteligente.interpretar_documento(
        "CARTEIRA NACIONAL DE HABILITACAO REGISTRO 12345678901"
    )

    assert chamada["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert chamada["payload"]["model"] == "openai/gpt-oss-20b"
    assert resultado["categoria"] == "CNH"
    assert resultado["engine"] == "openai/gpt-oss-20b"


def test_ocr_local_aplica_caminho_do_tesseract_configurado(app, monkeypatch):
    engine = ocr_local.pytesseract.pytesseract
    monkeypatch.setattr(engine, "tesseract_cmd", "antes")
    app.config["TESSERACT_CMD"] = "/usr/local/bin/tesseract-test"

    with app.app_context():
        ocr_local._configure_tesseract()

    assert engine.tesseract_cmd == "/usr/local/bin/tesseract-test"
