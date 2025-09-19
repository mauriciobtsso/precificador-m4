from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from datetime import datetime
import os

# ---------------------------
# Função auxiliar: formata moeda
# ---------------------------
def format_brl(value: float) -> str:
    """Formata número no padrão brasileiro de moeda (R$ 1.234,56)."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------------------
# Função auxiliar: carrega logo sem distorcer
# ---------------------------
def logo_flowable(path, max_w=140, max_h=48):
    """
    Carrega a imagem e redimensiona para caber no box (max_w x max_h),
    preservando a proporção.
    """
    try:
        ir = ImageReader(path)
        iw, ih = ir.getSize()
        scale = min(max_w / iw, max_h / ih)
        w, h = iw * scale, ih * scale
        return Image(path, width=w, height=h)
    except Exception:
        return Paragraph(
            "[logo não encontrada em app/static/img/logo_pedido.png]",
            getSampleStyleSheet()['Normal']
        )

# ---------------------------
# Palavras-chave para classificar itens
# ---------------------------
MAPA_TIPOS = {
    "armas": [
        "rifl", "rifle", "pist", "pistola",
        "rev", "revolver", "car", "carabina",
        "esp", "espingarda"
    ],
    "municoes": [
        "mun", "munição", "cart", "cartucho",
        "espol", "espoleta", "esto", "estojo",
        "polv", "pólvora"
    ],
}

def identificar_tipo(descricao: str) -> str:
    """Classifica item em armas, munições ou outros, com base na descrição."""
    d = descricao.lower()
    for tipo, chaves in MAPA_TIPOS.items():
        if any(ch in d for ch in chaves):
            return tipo
    return "outros"

# ---------------------------
# Função principal: gerar Pedido PDF
# ---------------------------
def gerar_pedido_m4(
    itens,                          # lista de tuplas: (codigo, descricao, qtd, unitario)
    cond_pagto="À vista",
    perc_armas=-5.0,
    perc_municoes=-3.0,
    perc_unico=0.0,
    modo="por_tipo",                 # "por_tipo" ou "unico"
    numero_pedido=None,
    data_pedido=None,
    fornecedor_nome="Fornecedor não informado",
    fornecedor_cnpj="-",
    fornecedor_endereco="-",
    fornecedor_cr="-"
):
    """
    Gera o PDF do pedido de compra (pedido_m4.pdf).
    Espera `itens` no formato [(codigo, descricao, quantidade, valor_unitario), ...].
    """

    # Configuração do documento
    doc = SimpleDocTemplate(
        "pedido_m4.pdf",
        pagesize=A4,
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30
    )
    styles = getSampleStyleSheet()
    story = []

    # =======================
    # Cabeçalho (logo + dados da loja lado a lado)
    # =======================
    logo_path = os.path.join("app", "static", "img", "logo_pedido.png")
    logo = logo_flowable(logo_path, max_w=140, max_h=48)

    dados_loja = [
        Paragraph("<b>M4 Tática Comércio e Serviços Ltda</b>", styles['Heading3']),
        Paragraph("CNPJ: 41.654.218/0001-47  -  CR nº 635069 - 10ª RM", styles['Normal']),
        Paragraph("Av. Universitária, 750, Lj 23 Edif Diamond Center, Teresina-PI, CEP 64049-494", styles['Normal']),
        Paragraph("Tel: (86) 3025-5885  -  comercial@m4tatica.com.br", styles['Normal']),
    ]

    cabecalho = Table([[logo, dados_loja]], colWidths=[70, 465])
    cabecalho.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(cabecalho)
    story.append(Spacer(1, 12))

    # =======================
    # Fornecedor + Dados do Pedido
    # =======================
    numero_pedido = numero_pedido or datetime.now().strftime("%Y%m%d%H%M")
    data_pedido = data_pedido or datetime.now().strftime("%d/%m/%Y")

    bloco1 = [
        Paragraph(f"<b>Fornecedor:</b> {fornecedor_nome}", styles['Normal']),
        Paragraph(f"CNPJ: {fornecedor_cnpj}  -  {fornecedor_cr}", styles['Normal']),
        Paragraph(f"Endereço: {fornecedor_endereco}", styles['Normal']),
    ]

    bloco2 = [
        Paragraph(f"<b>Nº do Pedido:</b> {numero_pedido}", styles['Normal']),
        Paragraph(f"<b>Data do Pedido:</b> {data_pedido}", styles['Normal']),
        Paragraph(f"<b>Condição de Pagamento:</b> {cond_pagto}", styles['Normal']),
    ]

    tabela_dados = Table([[bloco1, bloco2]], colWidths=[310, 225])
    tabela_dados.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(tabela_dados)
    story.append(Spacer(1, 12))

    # =======================
    # Tabela de Itens
    # =======================
    cabec = ["Código", "Descrição", "Qtd", "R$ Unitário", "Desc./Acrésc. Unit", "R$ Total"]
    data = [cabec]

    total_bruto = 0.0
    total_desc = 0.0

    for cod, desc, qtd, unit in itens:
        if modo == "unico":
            pct = perc_unico
        else:
            tipo = identificar_tipo(desc)
            pct = perc_armas if tipo == "armas" else (perc_municoes if tipo == "municoes" else 0.0)

        # Fórmula corrigida: aplica coeficiente
        coef = 1 + (pct / 100.0)
        unit_final = unit * coef
        desc_unit = unit_final - unit  # diferença aplicada (pode ser negativa)
        total_item = unit_final * qtd

        total_bruto += unit * qtd
        total_desc += desc_unit * qtd

        data.append([
            str(cod),
            desc,
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
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 10))

    # =======================
    # Totais
    # =======================
    total_final = total_bruto + total_desc

    if modo == "unico":
        story.append(Paragraph(f"<b>Percentual aplicado (único):</b> {perc_unico}%", styles['Normal']))
    else:
        story.append(Paragraph(f"<b>Percentual aplicado - Armas:</b> {perc_armas}%", styles['Normal']))
        story.append(Paragraph(f"<b>Percentual aplicado - Munições:</b> {perc_municoes}%", styles['Normal']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(f"<b>Valor Total dos Produtos:</b> {format_brl(total_bruto)}", styles['Normal']))
    story.append(Paragraph(f"<b>Diferença aplicada:</b> {format_brl(total_desc)}", styles['Normal']))
    story.append(Paragraph(f"<b>Valor Total Final:</b> {format_brl(total_final)}", styles['Normal']))

    doc.build(story)
    print("pedido_m4.pdf gerado com sucesso!")
