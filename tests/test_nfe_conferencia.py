from io import BytesIO

from pdfminer.high_level import extract_text

from app.admin.nfe_conferencia_routes import parse_nfe_for_review


SAMPLE_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe22260912345678000123550010000000011000000010" versao="4.00">
    <ide><nNF>1</nNF><serie>1</serie><dhEmi>2026-09-22T12:00:00-03:00</dhEmi></ide>
    <emit><xNome>Emitente de Teste Ltda</xNome></emit>
    <dest><xNome>Destinatario de Teste</xNome></dest>
    <det nItem="1"><prod><cProd>ABC-1</cProd><xProd>Produto sintético de teste</xProd><qCom>2</qCom><vUnCom>10.5000</vUnCom><vProd>21.00</vProd></prod></det>
    <total><ICMSTot><vProd>21.00</vProd><vNF>21.00</vNF></ICMSTot></total>
    <pag><detPag><tPag>01</tPag><vPag>21.00</vPag></detPag></pag>
  </infNFe></NFe>
  <protNFe><infProt><chNFe>22260912345678000123550010000000011000000010</chNFe></infProt></protNFe>
</nfeProc>'''.encode("utf-8")


def test_parser_extrai_apenas_campos_necessarios_para_conferencia():
    data = parse_nfe_for_review(SAMPLE_XML)
    assert data["number"] == "1"
    assert data["series"] == "1"
    assert data["issuer"] == "Emitente de Teste Ltda"
    assert data["recipient"] == "Destinatario de Teste"
    assert data["source_key"] == "22260912345678000123550010000000011000000010"
    assert data["total"] == "21.00"
    assert data["products_total"] == "21.00"
    assert data["payment_name"] == "Dinheiro"
    assert data["items"][0]["unit"] == "10.50"
    assert data["items"][0]["total"] == "21.00"


def test_parser_rejeita_xml_com_doctype_e_arquivo_acima_do_limite():
    import pytest

    with pytest.raises(ValueError, match="declarações proibidas"):
        parse_nfe_for_review(b'<!DOCTYPE x [<!ENTITY y "boom">]><x/>')

    with pytest.raises(ValueError, match="2 MB"):
        parse_nfe_for_review(b" " * (2 * 1024 * 1024 + 1))


def test_upload_preenche_editor_e_relatorio_pdf_mantem_aviso_nao_fiscal(client):
    upload = client.post(
        "/admin/nfe/conferencia",
        data={"xml": (BytesIO(SAMPLE_XML), "nota.xml")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200
    html = upload.get_data(as_text=True)
    assert "Emitente de Teste Ltda" in html
    assert "Chave lida do XML" in html
    assert "não gera danfe" in html.lower()
    assert "RASCUNHO — SEM VALOR FISCAL" in html

    key = "22260912345678000123550010000000011000000010"
    report = client.post("/admin/nfe/conferencia", data={
        "action": "report",
        "number": "1",
        "series": "1",
        "issuer": "Emitente de Teste Ltda",
        "recipient": "Destinatario de Teste",
        "source_key": key,
        "suggested_key": key,
        "total_original": "21.00",
        "total_sugerido": "20.00",
        "products_original": "21.00",
        "produtos_sugerido": "20.00",
        "payment_original": "21.00",
        "pagamento_sugerido": "20.00",
        "payment_name": "Dinheiro",
        "suggested_payment_name": "Dinheiro",
        "item_code": ["ABC-1"],
        "item_description": ["Produto sintético de teste"],
        "item_quantity": ["2"],
        "item_unit_original": ["10.50"],
        "item_total_original": ["21.00"],
        "item_unit_proposed": ["10.00"],
        "item_total_proposed": ["20.00"],
    })
    assert report.status_code == 200
    assert report.mimetype == "application/pdf"
    assert report.headers["Cache-Control"] == "no-store"
    assert report.data.startswith(b"%PDF-")
    assert "relatorio_interno_conferencia_nfe.pdf" in report.headers["Content-Disposition"]
    pdf_text = extract_text(BytesIO(report.data))
    assert "RASCUNHO — SEM VALOR FISCAL" in pdf_text
    assert "NÃO É DANFE" in pdf_text
    assert "21.00" in pdf_text and "20.00" in pdf_text


def test_relatorio_rejeita_chave_sugerida_invalida(client):
    response = client.post("/admin/nfe/conferencia", data={
        "action": "report",
        "number": "1", "series": "1", "issuer": "Emitente", "recipient": "Destinatario",
        "source_key": "", "suggested_key": "chave-invalida",
        "total_original": "1.00", "total_sugerido": "1.00",
        "products_original": "1.00", "produtos_sugerido": "1.00",
        "payment_original": "1.00", "pagamento_sugerido": "1.00",
        "payment_name": "Dinheiro", "suggested_payment_name": "Dinheiro",
        "item_code": ["A"], "item_description": ["Teste"], "item_quantity": ["1"],
        "item_unit_original": ["1.00"], "item_total_original": ["1.00"],
        "item_unit_proposed": ["1.00"], "item_total_proposed": ["1.00"],
    })
    assert response.status_code == 400
    assert "chave sugerida" in response.get_data(as_text=True).lower()
