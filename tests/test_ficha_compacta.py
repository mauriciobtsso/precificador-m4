from io import BytesIO
from uuid import uuid4

import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app import db
from app.clientes.models import Arma, Cliente, Documento
from app.clientes.ficha_compacta import FichaCompactaError, montar_ficha_compacta
from app.clientes.routes import ficha_documentos as ficha_routes


def _pdf_sintetico(paginas=1, largura=595, altura=842):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(largura, altura))
    for index in range(paginas):
        pdf.drawString(40, altura - 50, f"DOCUMENTO SINTETICO {index + 1}")
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def _imagem_sintetica():
    from PIL import Image

    output = BytesIO()
    image = Image.new("RGB", (320, 200), "white")
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


def test_ficha_compacta_gera_uma_unica_pagina_a4():
    dados = [
        ("CNH", _pdf_sintetico(1), "cnh.pdf"),
        ("CR", _pdf_sintetico(2), "cr.pdf"),
        ("CRAF", _imagem_sintetica(), "craf.png"),
    ]

    resultado = montar_ficha_compacta(dados)
    documento = pdfium.PdfDocument(resultado)
    try:
        assert len(documento) == 1
        assert documento[0].get_size() == pytest.approx(A4, abs=1)
    finally:
        documento.close()


def test_ficha_recusa_arquivo_com_mais_de_duas_paginas():
    dados = [
        ("CNH", _pdf_sintetico(3), "cnh.pdf"),
        ("CR", _pdf_sintetico(1), "cr.pdf"),
        ("CRAF", _pdf_sintetico(1), "craf.pdf"),
    ]

    with pytest.raises(FichaCompactaError, match="no máximo 2 páginas"):
        montar_ficha_compacta(dados)


def _criar_cliente_com_documentos():
    sufixo = str(uuid4().int % 10_000_000_000).zfill(10)
    cliente = Cliente(nome="Cliente Sintético", documento=f"1{sufixo}")
    db.session.add(cliente)
    db.session.flush()

    cnh = Documento(
        cliente_id=cliente.id,
        tipo="CNH",
        categoria="CNH",
        caminho_arquivo=f"clientes/{cliente.id}/documentos/cnh.pdf",
        nome_original="cnh-sintetica.pdf",
    )
    cr = Documento(
        cliente_id=cliente.id,
        tipo="CR",
        categoria="CR",
        caminho_arquivo=f"clientes/{cliente.id}/documentos/cr.pdf",
        nome_original="cr-sintetico.pdf",
    )
    arma = Arma(
        cliente_id=cliente.id,
        tipo="pistola",
        modelo="Modelo Sintético",
        calibre="9 mm",
        caminho_craf=f"clientes/{cliente.id}/armas/craf.pdf",
    )
    db.session.add_all([cnh, cr, arma])
    db.session.commit()
    return cliente, cnh, cr, arma


def test_rota_gera_previa_privada_sem_gravar_arquivo(app, client, monkeypatch):
    with app.app_context():
        cliente, cnh, cr, arma = _criar_cliente_com_documentos()
        ids = (cliente.id, cnh.id, cr.id, arma.id)

    fontes = {
        f"clientes/{ids[0]}/documentos/cnh.pdf": _pdf_sintetico(1),
        f"clientes/{ids[0]}/documentos/cr.pdf": _pdf_sintetico(2),
        f"clientes/{ids[0]}/armas/craf.pdf": _pdf_sintetico(2),
    }
    monkeypatch.setattr(ficha_routes, "_ler_arquivo_r2", lambda caminho, cliente_id: fontes[caminho])

    resposta = client.post(
        f"/clientes/{ids[0]}/documentos/ficha-compacta",
        data={
            "cnh_id": str(ids[1]),
            "cr_id": str(ids[2]),
            "arma_id": str(ids[3]),
            "confirmar_conferencia": "1",
            "acao": "visualizar",
        },
    )

    assert resposta.status_code == 200
    assert resposta.mimetype == "application/pdf"
    assert resposta.headers["Content-Disposition"].startswith("inline;")
    assert "no-store" in resposta.headers["Cache-Control"]
    assert resposta.data.startswith(b"%PDF-")
    pdf = pdfium.PdfDocument(resposta.data)
    try:
        assert len(pdf) == 1
    finally:
        pdf.close()


def test_rota_nao_aceita_documento_de_outro_cliente(app, client, monkeypatch):
    with app.app_context():
        cliente_a, _cnh_a, cr_a, arma_a = _criar_cliente_com_documentos()
        cliente_b, cnh_b, _cr_b, _arma_b = _criar_cliente_com_documentos()
        ids = (cliente_a.id, cnh_b.id, cr_a.id, arma_a.id)
        cliente_b_id = cliente_b.id

    monkeypatch.setattr(
        ficha_routes,
        "_ler_arquivo_r2",
        lambda *_args: pytest.fail("Não deve acessar o storage após rejeitar documento alheio"),
    )
    resposta = client.post(
        f"/clientes/{ids[0]}/documentos/ficha-compacta",
        data={
            "cnh_id": str(ids[1]),
            "cr_id": str(ids[2]),
            "arma_id": str(ids[3]),
            "confirmar_conferencia": "1",
        },
    )

    assert resposta.status_code == 302
    assert f"/clientes/{ids[0]}" in resposta.headers["Location"]
    assert cliente_b_id != ids[0]


def test_rota_exige_login(app, client):
    login_disabled_anterior = app.config.get("LOGIN_DISABLED", False)
    app.config["LOGIN_DISABLED"] = False
    try:
        resposta = client.post("/clientes/987654321/documentos/ficha-compacta")
    finally:
        app.config["LOGIN_DISABLED"] = login_disabled_anterior

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]
