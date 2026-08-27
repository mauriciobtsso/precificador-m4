# app/utils/gerar_pedidos.py
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.utils import ImageReader


M4_BLACK = colors.HexColor("#17191c")
M4_GOLD = colors.HexColor("#b58a3a")
M4_GOLD_LIGHT = colors.HexColor("#f7f1e5")
M4_TEXT = colors.HexColor("#252b33")
M4_MUTED = colors.HexColor("#697381")
M4_BORDER = colors.HexColor("#dfe4ea")
M4_ROW = colors.HexColor("#f8fafc")


def format_brl(value: float) -> str:
    """Formata número no padrão brasileiro de moeda."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_pct(value: float) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.2f}%".replace(".", ",")


def logo_flowable(path, max_w=33 * mm, max_h=18 * mm):
    """Carrega a logo mantendo proporção e oferece fallback textual seguro."""
    try:
        image_reader = ImageReader(str(path))
        image_w, image_h = image_reader.getSize()
        scale = min(max_w / image_w, max_h / image_h)
        image = Image(str(path), width=image_w * scale, height=image_h * scale)
        image.hAlign = "LEFT"
        return image
    except Exception:
        return Paragraph("<b>M4 TÁTICA</b>", ParagraphStyle("LogoFallback", fontSize=13, textColor=M4_BLACK))


MAPA_TIPOS = {
    "armas": ["rifl", "rifle", "pist", "pistola", "rev", "revolver", "car", "carabina", "esp", "espingarda"],
    "municoes": ["mun", "munição", "cart", "cartucho", "espol", "espoleta", "esto", "estojo", "polv", "pólvora"],
}


def identificar_tipo(descricao: str) -> str:
    descricao_normalizada = str(descricao or "").lower()
    for tipo, palavras in MAPA_TIPOS.items():
        if any(palavra in descricao_normalizada for palavra in palavras):
            return tipo
    return "outros"


def _safe(value) -> str:
    return escape(str(value or "-"))


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="M4Body", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=M4_TEXT))
    styles.add(ParagraphStyle(name="M4Small", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9, textColor=M4_MUTED))
    styles.add(ParagraphStyle(name="M4SmallDark", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9, textColor=M4_TEXT))
    styles.add(ParagraphStyle(name="M4Label", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=M4_MUTED, uppercase=True))
    styles.add(ParagraphStyle(name="M4Title", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=M4_BLACK))
    styles.add(ParagraphStyle(name="M4Section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=M4_BLACK))
    styles.add(ParagraphStyle(name="M4Table", parent=styles["Normal"], fontName="Helvetica", fontSize=7.4, leading=9, textColor=M4_TEXT))
    styles.add(ParagraphStyle(name="M4TableBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.4, leading=9, textColor=M4_TEXT))
    styles.add(ParagraphStyle(name="M4TableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=8.5, alignment=TA_CENTER, textColor=colors.white))
    styles.add(ParagraphStyle(name="M4Right", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, alignment=TA_RIGHT, textColor=M4_TEXT))
    styles.add(ParagraphStyle(name="M4RightBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_RIGHT, textColor=M4_BLACK))
    return styles


def _footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(M4_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 6.8)
    canvas.setFillColor(M4_MUTED)
    canvas.drawString(18 * mm, 9 * mm, "M4 Tática · Documento comercial para conferência do fornecedor")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"Página {doc.page}")
    canvas.restoreState()


def gerar_pedido_m4(
    itens: Iterable,
    cond_pagto="À vista",
    perc_armas=-5.0,
    perc_municoes=-3.0,
    perc_unico=0.0,
    modo="por_tipo",
    numero_pedido=None,
    data_pedido=None,
    fornecedor_nome="Fornecedor não informado",
    fornecedor_cnpj="-",
    fornecedor_endereco="-",
    fornecedor_cr="-",
    fornecedor_contato="-",
    output_path="pedido_m4.pdf",
):
    """Gera um pedido de compra PDF com layout comercial e retorna o arquivo gerado."""
    styles = _styles()
    numero_pedido = numero_pedido or datetime.now().strftime("%Y%m%d%H%M")
    data_pedido = data_pedido or datetime.now().strftime("%d/%m/%Y")
    output_path = str(output_path or "pedido_m4.pdf")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title=f"Pedido de compra {numero_pedido}",
        author="M4 Tática",
    )

    story = []
    logo_path = Path(__file__).resolve().parents[1] / "static" / "img" / "logo_pedido.png"
    logo = logo_flowable(logo_path)
    company = [
        Paragraph("<b>M4 TÁTICA COMÉRCIO E SERVIÇOS LTDA</b>", styles["M4Body"]),
        Paragraph("CNPJ: 41.654.218/0001-47 · CR nº 635069 · 10ª RM", styles["M4Small"]),
        Paragraph("Av. Universitária, 750, Lj 23 · Teresina-PI · CEP 64049-494", styles["M4Small"]),
        Paragraph("(86) 3025-5885 · comercial@m4tatica.com.br", styles["M4Small"]),
    ]
    header = Table([[logo, company, Paragraph("<b>PEDIDO DE COMPRA</b>", styles["M4Title"])]], colWidths=[38 * mm, 92 * mm, 54 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([header, Spacer(1, 4 * mm)])

    order_meta = Table([
        [Paragraph("NÚMERO", styles["M4Label"]), Paragraph("DATA", styles["M4Label"]), Paragraph("CONDIÇÃO DE PAGAMENTO", styles["M4Label"])],
        [Paragraph(f"<b>{_safe(numero_pedido)}</b>", styles["M4Body"]), Paragraph(f"<b>{_safe(data_pedido)}</b>", styles["M4Body"]), Paragraph(f"<b>{_safe(cond_pagto)}</b>", styles["M4Body"])],
    ], colWidths=[50 * mm, 40 * mm, 94 * mm])
    order_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), M4_GOLD_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.7, M4_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, M4_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.extend([order_meta, Spacer(1, 4 * mm)])

    supplier = [
        Paragraph("<b>FORNECEDOR</b>", styles["M4Section"]),
        Paragraph(f"<b>{_safe(fornecedor_nome)}</b>", styles["M4Body"]),
        Paragraph(f"CNPJ: {_safe(fornecedor_cnpj)}", styles["M4SmallDark"]),
        Paragraph(f"CR: {_safe(fornecedor_cr)}", styles["M4SmallDark"]),
    ]
    supplier_contact = [
        Paragraph("<b>CONTATO E ENTREGA</b>", styles["M4Section"]),
        Paragraph(f"{_safe(fornecedor_endereco)}", styles["M4SmallDark"]),
        Paragraph(f"Contato: {_safe(fornecedor_contato)}", styles["M4SmallDark"]),
    ]
    supplier_table = Table([[supplier, supplier_contact]], colWidths=[92 * mm, 92 * mm])
    supplier_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, M4_BORDER),
        ("LINEBEFORE", (1, 0), (1, 0), 0.7, M4_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    story.extend([supplier_table, Spacer(1, 5 * mm), Paragraph("ITENS DO PEDIDO", styles["M4Section"]), Spacer(1, 2 * mm)])

    headers = ["Código", "Descrição", "Qtd.", "Valor unitário", "Ajuste unitário", "Total"]
    data = [[Paragraph(_safe(header), styles["M4TableHeader"]) for header in headers]]
    total_bruto = 0.0
    total_ajuste = 0.0
    itens = list(itens or [])
    for codigo, descricao, quantidade, unitario in itens:
        descricao = descricao or "-"
        try:
            qtd = int(quantidade or 0)
        except (TypeError, ValueError):
            qtd = 0
        try:
            unit = float(unitario or 0)
        except (TypeError, ValueError):
            unit = 0.0
        if modo == "unico":
            percentual = float(perc_unico or 0)
        else:
            tipo = identificar_tipo(descricao)
            percentual = float(perc_armas or 0) if tipo == "armas" else (float(perc_municoes or 0) if tipo == "municoes" else 0.0)
        unit_final = unit * (1 + percentual / 100)
        ajuste_unitario = unit_final - unit
        total_item = unit_final * qtd
        total_bruto += unit * qtd
        total_ajuste += ajuste_unitario * qtd
        data.append([
            Paragraph(_safe(codigo), styles["M4Table"]),
            Paragraph(_safe(descricao), styles["M4Table"]),
            Paragraph(str(qtd), ParagraphStyle("Qtd", parent=styles["M4Table"], alignment=TA_CENTER)),
            Paragraph(format_brl(unit), ParagraphStyle("Unit", parent=styles["M4Table"], alignment=TA_RIGHT)),
            Paragraph(format_brl(ajuste_unitario), ParagraphStyle("Ajuste", parent=styles["M4Table"], alignment=TA_RIGHT)),
            Paragraph(format_brl(total_item), ParagraphStyle("Total", parent=styles["M4TableBold"], alignment=TA_RIGHT)),
        ])

    items_table = LongTable(data, colWidths=[20 * mm, 65 * mm, 15 * mm, 27 * mm, 31 * mm, 26 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), M4_BLACK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, M4_ROW]),
        ("BOX", (0, 0), (-1, -1), 0.7, M4_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, M4_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.extend([items_table, Spacer(1, 5 * mm)])

    total_final = total_bruto + total_ajuste
    adjustment_label = "Percentual único" if modo == "unico" else "Armas / munições"
    adjustment_value = format_pct(perc_unico) if modo == "unico" else f"{format_pct(perc_armas)} / {format_pct(perc_municoes)}"
    totals = Table([
        [Paragraph("CONDIÇÃO COMERCIAL", styles["M4Label"]), Paragraph("RESUMO FINANCEIRO", styles["M4Label"])],
        [Paragraph(f"<b>{_safe(adjustment_label)}</b><br/>Aplicação: {_safe(adjustment_value)}", styles["M4SmallDark"]), [
            Paragraph(f"Produtos: {format_brl(total_bruto)}", styles["M4Right"]),
            Paragraph(f"Ajustes: {format_brl(total_ajuste)}", styles["M4Right"]),
            Paragraph(f"<b>TOTAL FINAL: {format_brl(total_final)}</b>", styles["M4RightBold"]),
        ]],
    ], colWidths=[82 * mm, 102 * mm])
    totals.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), M4_GOLD_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.7, M4_BORDER),
        ("LINEBEFORE", (1, 0), (1, -1), 0.7, M4_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.extend([totals, Spacer(1, 5 * mm), Paragraph("Documento comercial sujeito à conferência de disponibilidade, valores, condição de pagamento e demais condições acordadas entre as partes. Não substitui nota fiscal.", styles["M4Small"])])

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
