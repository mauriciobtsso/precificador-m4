# app/utils/gerar_pedidos.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from datetime import datetime
import os


# ====================================================
# FUNÇÕES AUXILIARES
# ====================================================
def format_brl(value: float) -> str:
    """Formata número no padrão brasileiro de moeda (R$ 1.234,56)."""
    if value is None:
        value = 0.0
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def logo_flowable(path, max_w=120, max_h=46):
    """Carrega a imagem e redimensiona para caber no box (max_w x max_h)."""
    try:
        ir = ImageReader(path)
        iw, ih = ir.getSize()
        scale = min(max_w / iw, max_h / ih)
        w, h = iw * scale, ih * scale
        img = Image(path, width=w, height=h)
        img.hAlign = 'LEFT'  # 🔧 força alinhamento total à esquerda
        return img
    except Exception:
        return Paragraph(
            "[logo não encontrada em app/static/img/logo_pedido.png]",
            getSampleStyleSheet()['Normal']
        )


# Palavras-chave para classificar itens
MAPA_TIPOS = {
    "armas": ["rifl", "rifle", "pist", "pistola", "rev", "revolver", "car", "carabina", "esp", "espingarda"],
    "municoes": ["mun", "munição", "cart", "cartucho", "espol", "espoleta", "esto", "estojo", "polv", "pólvora"],
}

def identificar_tipo(descricao: str) -> str:
    """Classifica item em armas, munições ou outros, com base na descrição."""
    if not descricao:
        return "outros"
    d = descricao.lower()
    for tipo, chaves in MAPA_TIPOS.items():
        if any(ch in d for ch in chaves):
            return tipo
    return "outros"


# ====================================================
# FUNÇÃO PRINCIPAL — GERAR PEDIDO M4
# ====================================================
def gerar_pedido_m4(
    itens,
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
    fornecedor_contato="-"
):
    """Gera o PDF do pedido de compra (pedido_m4.pdf)."""
    doc = SimpleDocTemplate(
        "pedido_m4.pdf",
        pagesize=A4,
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='NormalSmall', fontSize=8, leading=10))
    styles.add(ParagraphStyle(name='NormalLeft', alignment=0, fontSize=9, leading=11))
    styles.add(ParagraphStyle(name='BoldLeft', alignment=0, fontSize=9, leading=11, spaceBefore=4, spaceAfter=2))
    styles.add(ParagraphStyle(name='Tabela', fontSize=8, leading=9))

    story = []

    # ====================================================
    # 01. CABEÇALHO (LOGO + DADOS LOJA)
    # ====================================================
    logo_path = os.path.join("app", "static", "img", "logo_pedido.png")
    logo = logo_flowable(logo_path, max_w=120, max_h=46)

    dados_loja = [
        Paragraph("<b>M4 TÁTICA COMÉRCIO E SERVIÇOS LTDA</b>", styles['BoldLeft']),
        Paragraph("CNPJ: 41.654.218/0001-47  —  CR nº 635069 — 10ª RM", styles['NormalSmall']),
        Paragraph("Av. Universitária, 750, Lj 23 Edif. Diamond Center, Teresina-PI, CEP 64049-494", styles['NormalSmall']),
        Paragraph("Tel: (86) 3025-5885  |  comercial@m4tatica.com.br", styles['NormalSmall']),
    ]

    # 🔧 Alinhamento refinado — elimina o espaço entre logo e texto
    cabecalho = Table([[logo, dados_loja]], colWidths=[90, 450])
    cabecalho.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(cabecalho)
    story.append(Spacer(1, 8))

    # ====================================================
    # 02. FORNECEDOR (ESQUERDA) + 03. DADOS PEDIDO (DIREITA)
    # ====================================================
    story.append(Spacer(1, 14))  # 🔽 adiciona mais respiro após o cabeçalho

    numero_pedido = numero_pedido or datetime.now().strftime("%Y%m%d%H%M")
    data_pedido = data_pedido or datetime.now().strftime("%d/%m/%Y")

    fornecedor_nome = fornecedor_nome or "-"
    fornecedor_cnpj = fornecedor_cnpj or "-"
    fornecedor_endereco = fornecedor_endereco or "-"
    fornecedor_cr = fornecedor_cr or "-"
    fornecedor_contato = fornecedor_contato or "-"

    bloco1 = [
        Paragraph(f"<b>Fornecedor:</b> {fornecedor_nome}", styles['NormalLeft']),
        Paragraph(f"CNPJ: {fornecedor_cnpj}  —  {fornecedor_cr}", styles['NormalLeft']),
        Paragraph(f"Endereço: {fornecedor_endereco}", styles['NormalLeft']),
        Paragraph(f"Contato: {fornecedor_contato}", styles['NormalLeft']),
    ]

    bloco2 = [
        Paragraph(f"<b>Nº do Pedido:</b> {numero_pedido}", styles['NormalLeft']),
        Paragraph(f"<b>Data do Pedido:</b> {data_pedido}", styles['NormalLeft']),
        Paragraph(f"<b>Condição de Pagamento:</b> {cond_pagto}", styles['NormalLeft']),
    ]

    # 🔧 alinhamento refinado: direita agora acompanha "Desc./Acrésc. Unit"
    # A tabela total tem 525 pt (colWidths da tabela principal somam 560, menos padding)
    # "Desc./Acrésc. Unit" começa aproximadamente no 480–490 pt da margem esquerda.
    tabela_dados = Table([[bloco1, bloco2]], colWidths=[315, 215])
    tabela_dados.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 3),   # 🔽 empurra levemente para baixo
    ]))
    story.append(tabela_dados)
    story.append(Spacer(1, 6))

    # ====================================================
    # 04. TABELA DE ITENS (com quebra automática)
    # ====================================================
    cabec = ["Código", "Descrição", "Qtd", "R$ Unitário", "Desc./Acrésc. Unit", "R$ Total"]
    data = [cabec]
    total_bruto = 0.0
    total_desc = 0.0

    for cod, desc, qtd, unit in itens:
        cod = cod or "-"
        desc = desc or "-"
        qtd = qtd or 0
        unit = unit or 0.0

        if modo == "unico":
            pct = perc_unico or 0.0
        else:
            tipo = identificar_tipo(desc)
            pct = perc_armas if tipo == "armas" else (perc_municoes if tipo == "municoes" else 0.0)

        coef = 1 + (pct / 100.0)
        unit_final = unit * coef
        desc_unit = unit_final - unit
        total_item = unit_final * qtd

        total_bruto += unit * qtd
        total_desc += desc_unit * qtd

        data.append([
            str(cod),
            Paragraph(desc, styles['Tabela']),
            str(qtd),
            format_brl(unit),
            format_brl(desc_unit),
            format_brl(total_item),
        ])

    tabela = Table(data, colWidths=[60, 210, 45, 75, 90, 80])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 12))

    # ====================================================
    # 05. TOTAIS
    # ====================================================
    total_final = total_bruto + total_desc

    story.append(Paragraph("<b>Resumo Desc./Acresc.:</b>", styles['BoldLeft']))
    if modo == "unico":
        story.append(Paragraph(f"Percentual aplicado (único): {perc_unico}%", styles['NormalLeft']))
    else:
        story.append(Paragraph(f"Percentual aplicado - Armas: {perc_armas}%", styles['NormalLeft']))
        story.append(Paragraph(f"Percentual aplicado - Munições: {perc_municoes}%", styles['NormalLeft']))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"<b>Valor Total dos Produtos:</b> {format_brl(total_bruto)}", styles['NormalLeft']))
    story.append(Paragraph(f"<b>Diferença aplicada:</b> {format_brl(total_desc)}", styles['NormalLeft']))
    story.append(Paragraph(f"<b>Valor Total Final:</b> {format_brl(total_final)}", styles['BoldLeft']))
    story.append(Spacer(1, 20))

    # ====================================================
    # GERAR PDF
    # ====================================================
    doc.build(story)
    print("pedido_m4.pdf gerado com sucesso!")
