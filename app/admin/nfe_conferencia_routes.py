"""Conferência interna de valores extraídos de XML de NF-e.

Este módulo deliberadamente não altera XML, assinatura, protocolo, chave oficial,
barcode ou QR Code, e não gera DANFE. O PDF é somente um relatório interno com
marca d'água, sem validade fiscal.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from datetime import datetime

from flask import flash, make_response, render_template, request
from flask_login import login_required
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

from app.admin import admin_bp

MAX_XML_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 100
MAX_MONEY = Decimal("999999999999.99")
PAYMENT_LABELS = {
    "01": "Dinheiro",
    "02": "Cheque",
    "03": "Cartão de crédito",
    "04": "Cartão de débito",
    "05": "Crédito loja",
    "10": "Vale alimentação",
    "11": "Vale refeição",
    "12": "Vale presente",
    "13": "Vale combustível",
    "15": "Boleto bancário",
    "16": "Depósito bancário",
    "17": "PIX",
    "18": "Transferência",
    "19": "Programa de fidelidade",
    "90": "Sem pagamento",
    "99": "Outros",
}


def _direct_child(node, local_name):
    if node is None:
        return None
    return next(
        (child for child in node if etree.QName(child).localname == local_name),
        None,
    )


def _text(node, local_name, default=""):
    child = _direct_child(node, local_name)
    return (child.text or "").strip() if child is not None else default


def _find_first(node, local_name):
    return next(
        (element for element in node.iter() if etree.QName(element).localname == local_name),
        None,
    )


def _money_xml(value):
    try:
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        amount = Decimal("0.00")
    return f"{amount:.2f}"


def parse_nfe_for_review(xml_bytes):
    """Extrai apenas os dados necessários à conferência, sem guardar o XML."""
    if not xml_bytes:
        raise ValueError("Selecione um arquivo XML.")
    if len(xml_bytes) > MAX_XML_BYTES:
        raise ValueError("O XML ultrapassa o limite de 2 MB.")
    upper = xml_bytes.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("O XML contém declarações proibidas e não pode ser processado.")

    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        remove_comments=True,
    )
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ValueError("Não foi possível ler o XML. Confira o arquivo enviado.") from exc
    if etree.QName(root).localname not in {"nfeProc", "NFe"}:
        raise ValueError("O arquivo não parece ser uma NF-e processada ou um XML NFe.")

    inf_nfe = _find_first(root, "infNFe")
    if inf_nfe is None:
        raise ValueError("O XML não contém o bloco infNFe esperado.")
    ide = _direct_child(inf_nfe, "ide")
    emit = _direct_child(inf_nfe, "emit")
    dest = _direct_child(inf_nfe, "dest")
    total_node = _direct_child(_direct_child(inf_nfe, "total"), "ICMSTot")
    payment = _find_first(inf_nfe, "detPag")
    key = (inf_nfe.get("Id") or "").removeprefix("NFe")
    if not key:
        key_node = _find_first(root, "chNFe")
        key = (key_node.text or "").strip() if key_node is not None else ""

    items = []
    for det in (node for node in inf_nfe.iter() if etree.QName(node).localname == "det"):
        product = _direct_child(det, "prod")
        if product is None:
            continue
        items.append({
            "code": _text(product, "cProd"),
            "description": _text(product, "xProd"),
            "quantity": _text(product, "qCom", "0"),
            "unit": _money_xml(_text(product, "vUnCom", "0")),
            "total": _money_xml(_text(product, "vProd", "0")),
        })
        if len(items) > MAX_ITEMS:
            raise ValueError(f"A conferência aceita no máximo {MAX_ITEMS} itens por XML.")

    if not items:
        raise ValueError("O XML não contém itens de produto reconhecíveis.")

    pay_code = _text(payment, "tPag") if payment is not None else ""
    payment_name = PAYMENT_LABELS.get(pay_code, f"Código {pay_code}" if pay_code else "Não informado")
    emission = _text(ide, "dhEmi") or _text(ide, "dEmi")
    return {
        "number": _text(ide, "nNF"),
        "series": _text(ide, "serie"),
        "emission": emission,
        "issuer": _text(emit, "xNome"),
        "recipient": _text(dest, "xNome"),
        "source_key": key,
        "total": _money_xml(_text(total_node, "vNF", "0")),
        "products_total": _money_xml(_text(total_node, "vProd", "0")),
        "payment_name": payment_name,
        "payment_value": _money_xml(_text(payment, "vPag", "0") if payment is not None else "0"),
        "items": items,
    }


def _submitted_money(value, label):
    try:
        amount = Decimal((value or "").strip())
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError(f"Valor inválido no campo {label}.")
    if not amount.is_finite() or amount < 0 or amount > MAX_MONEY:
        raise ValueError(f"Valor fora do limite permitido no campo {label}.")
    return amount


def _form_value(name, label):
    value = request.form.get(name, "").strip()
    if len(value) > 200:
        raise ValueError(f"O campo {label} excede o tamanho permitido.")
    return value


def _report_data_from_form():
    values = {
        "number": _form_value("number", "número"),
        "series": _form_value("series", "série"),
        "issuer": _form_value("issuer", "emitente"),
        "recipient": _form_value("recipient", "destinatário"),
        "source_key": _form_value("source_key", "chave original"),
        "suggested_key": _form_value("suggested_key", "chave sugerida"),
        "payment_name": _form_value("payment_name", "forma de pagamento original"),
        "suggested_payment_name": _form_value("suggested_payment_name", "forma de pagamento sugerida"),
    }
    for key_label, proposed_field in (
        ("total_original", "total_sugerido"),
        ("products_original", "produtos_sugerido"),
        ("payment_original", "pagamento_sugerido"),
    ):
        original = _form_value(key_label, key_label)
        values[key_label] = _submitted_money(original, key_label)
        values[proposed_field] = _submitted_money(request.form.get(proposed_field), proposed_field)

    key = values["suggested_key"]
    if key and (not key.isdigit() or len(key) != 44):
        raise ValueError("A chave sugerida deve ter 44 dígitos ou ficar vazia.")

    codes = request.form.getlist("item_code")
    descriptions = request.form.getlist("item_description")
    quantities = request.form.getlist("item_quantity")
    unit_originals = request.form.getlist("item_unit_original")
    totals_originals = request.form.getlist("item_total_original")
    unit_proposed = request.form.getlist("item_unit_proposed")
    totals_proposed = request.form.getlist("item_total_proposed")
    lengths = {len(codes), len(descriptions), len(quantities), len(unit_originals), len(totals_originals), len(unit_proposed), len(totals_proposed)}
    if len(lengths) != 1 or not codes or len(codes) > MAX_ITEMS:
        raise ValueError("A lista de itens está incompleta ou excede o limite permitido.")

    values["items"] = []
    for index in range(len(codes)):
        values["items"].append({
            "code": codes[index][:80],
            "description": descriptions[index][:500],
            "quantity": quantities[index][:40],
            "unit_original": _submitted_money(unit_originals[index], f"item {index + 1} original").quantize(Decimal("0.01")),
            "total_original": _submitted_money(totals_originals[index], f"total do item {index + 1} original").quantize(Decimal("0.01")),
            "unit_proposed": _submitted_money(unit_proposed[index], f"item {index + 1} sugerido").quantize(Decimal("0.01")),
            "total_proposed": _submitted_money(totals_proposed[index], f"total do item {index + 1} sugerido").quantize(Decimal("0.01")),
        })
    return values


class _WatermarkCanvas(Canvas):
    """Marca d'água impressa em todas as páginas do relatório interno."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.saveState()
            self.setFillColor(colors.Color(0.78, 0.12, 0.12, alpha=0.16))
            self.setFont("Helvetica-Bold", 28)
            self.translate(A4[0] / 2, A4[1] / 2)
            self.rotate(35)
            self.drawCentredString(0, 0, "RASCUNHO — SEM VALOR FISCAL")
            self.restoreState()
            super().showPage()
        super().save()


def _paragraph(text, style):
    return Paragraph(escape(str(text or "—")), style)


def build_internal_report(data):
    """Gera relatório de divergências, visualmente distinto de DANFE."""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="Relatório interno de conferência de NF-e — sem valor fiscal",
        author="M4 Tática — relatório interno",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InternalTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=17, leading=21, alignment=TA_LEFT, textColor=colors.HexColor("#242424"),
        spaceAfter=7 * mm,
    ))
    styles.add(ParagraphStyle(
        name="Notice", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=10, leading=14, alignment=TA_CENTER,
        textColor=colors.HexColor("#8b1e1e"), borderColor=colors.HexColor("#8b1e1e"),
        borderWidth=1, borderPadding=8, spaceAfter=7 * mm,
    ))
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="SectionHead", parent=styles["Heading2"], fontSize=11, leading=14, spaceBefore=4 * mm, spaceAfter=2 * mm))

    story = [
        Paragraph("RELATÓRIO INTERNO DE CONFERÊNCIA", styles["InternalTitle"]),
        Paragraph("RASCUNHO — SEM VALOR FISCAL<br/>NÃO É DANFE, NÃO É NF-e E NÃO COMPROVA AUTORIZAÇÃO", styles["Notice"]),
        Paragraph("Identificação da fonte", styles["SectionHead"]),
    ]
    source_rows = [
        ["NF-e de referência", f"Nº {data['number'] or '—'}  •  Série {data['series'] or '—'}"],
        ["Emitente", data["issuer"] or "—"],
        ["Destinatário", data["recipient"] or "—"],
        ["Chave lida do XML", data["source_key"] or "Não informada"],
    ]
    source_table = Table(source_rows, colWidths=[43 * mm, 133 * mm], repeatRows=0, hAlign="LEFT")
    source_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([source_table, Paragraph("Valores conferidos (original × sugestão interna)", styles["SectionHead"])])
    summary_rows = [
        ["Campo", "Valor no XML informado", "Sugestão para conferência"],
        ["Total da NF-e", f"R$ {data['total_original']:.2f}", f"R$ {data['total_sugerido']:.2f}"],
        ["Total dos produtos", f"R$ {data['products_original']:.2f}", f"R$ {data['produtos_sugerido']:.2f}"],
        ["Pagamento", data["payment_name"] or "—", data["suggested_payment_name"] or "—"],
        ["Valor do pagamento", f"R$ {data['payment_original']:.2f}", f"R$ {data['pagamento_sugerido']:.2f}"],
        ["Chave de acesso", data["source_key"] or "—", data["suggested_key"] or "Sem sugestão"],
    ]
    summary = Table(
        [[_paragraph(cell, styles["SmallCell"]) for cell in row] for row in summary_rows],
        colWidths=[48 * mm, 62 * mm, 66 * mm], repeatRows=1, hAlign="LEFT",
    )
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dedede")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([summary, Paragraph("Itens (original × sugestão interna)", styles["SectionHead"])])
    item_rows = [["Código / descrição", "Qtd.", "Unitário XML", "Unitário sugerido", "Total XML", "Total sugerido"]]
    for item in data["items"]:
        item_rows.append([
            _paragraph(f"{item['code']} — {item['description']}", styles["SmallCell"]),
            _paragraph(item["quantity"], styles["SmallCell"]),
            _paragraph(f"R$ {item['unit_original']:.2f}", styles["SmallCell"]),
            _paragraph(f"R$ {item['unit_proposed']:.2f}", styles["SmallCell"]),
            _paragraph(f"R$ {item['total_original']:.2f}", styles["SmallCell"]),
            _paragraph(f"R$ {item['total_proposed']:.2f}", styles["SmallCell"]),
        ])
    item_table = Table(
        item_rows,
        colWidths=[54 * mm, 13 * mm, 25 * mm, 27 * mm, 25 * mm, 27 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dedede")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aaaaaa")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([
        item_table,
        Spacer(1, 6 * mm),
        Paragraph(
            "Este relatório não altera o XML original nem valida assinatura digital, chave, protocolo ou autorização. "
            "Para corrigir uma NF-e autorizada, solicite orientação ao responsável fiscal e use o procedimento "
            "oficial cabível junto ao emissor/SEFAZ. Nenhum código de barras ou QR Code é criado neste relatório.",
            styles["SmallCell"],
        ),
        Spacer(1, 3 * mm),
        Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — documento interno para revisão.", styles["SmallCell"]),
    ])
    doc.build(story, canvasmaker=_WatermarkCanvas)
    output.seek(0)
    return output


@admin_bp.route("/nfe/conferencia", methods=["GET", "POST"], endpoint="nfe_conferencia")
@login_required
def nfe_conferencia():
    if request.method == "GET":
        response = make_response(render_template("admin/nfe_conferencia.html", data=None))
        response.headers["Cache-Control"] = "no-store"
        return response

    if request.form.get("action") == "report":
        try:
            data = _report_data_from_form()
            pdf = build_internal_report(data)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("admin/nfe_conferencia.html", data=None), 400
        response = make_response(pdf.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = 'attachment; filename="relatorio_interno_conferencia_nfe.pdf"'
        response.headers["Cache-Control"] = "no-store"
        return response

    upload = request.files.get("xml")
    if upload is None or not upload.filename:
        flash("Selecione um arquivo XML para iniciar a conferência.", "warning")
        return render_template("admin/nfe_conferencia.html", data=None), 400
    try:
        xml_bytes = upload.stream.read(MAX_XML_BYTES + 1)
        data = parse_nfe_for_review(xml_bytes)
    except ValueError as exc:
        flash(str(exc), "danger")
        return render_template("admin/nfe_conferencia.html", data=None), 400
    flash("XML lido em memória. Nenhuma cópia foi salva e nenhum dado oficial foi alterado.", "success")
    response = make_response(render_template("admin/nfe_conferencia.html", data=data))
    response.headers["Cache-Control"] = "no-store"
    return response
