from __future__ import annotations

import io
import html
import re
from datetime import date
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _endereco(cliente) -> str:
    endereco = next((item for item in (cliente.enderecos or []) if item.tipo == "residencial"), None)
    if not endereco:
        return ""
    partes = [endereco.logradouro, endereco.numero, endereco.complemento, endereco.bairro, endereco.cidade, endereco.estado, endereco.cep]
    return ", ".join(str(item).strip() for item in partes if item and str(item).strip())


def gerar_declaracao(cliente, tipo: str) -> bytes:
    if tipo not in {"residencia", "nao_inquerito"}:
        raise ValueError("Tipo de declaração inválido.")
    nome = html.escape(cliente.nome or "________________________________________")
    documento = html.escape(cliente.documento or "________________________")
    endereco = html.escape(_endereco(cliente) or "________________________________________")
    hoje = date.today().strftime("%d/%m/%Y")
    if tipo == "residencia":
        titulo = "DECLARAÇÃO DE RESIDÊNCIA"
        texto = f"Eu, <b>{nome}</b>, inscrito(a) no CPF/CNPJ sob o nº <b>{documento}</b>, declaro, para os devidos fins, que resido no endereço <b>{endereco}</b>. Declaro ainda que as informações acima são verdadeiras, estando ciente das responsabilidades legais decorrentes da falsidade desta declaração."
        chave_modelo = "declaracao_residencia"
    else:
        titulo = "DECLARAÇÃO DE NÃO RESPONDER A INQUÉRITO POLICIAL"
        texto = f"Eu, <b>{nome}</b>, inscrito(a) no CPF/CNPJ sob o nº <b>{documento}</b>, declaro, para os devidos fins, que não estou respondendo a inquérito policial, salvo se expressamente informado em documento próprio. Declaro que as informações prestadas são verdadeiras e assumo responsabilidade por seu conteúdo."
        chave_modelo = "declaracao_nao_inquerito"

    try:
        from app.models import ModeloDocumento
        modelo = ModeloDocumento.query.filter_by(chave=chave_modelo).first()
        if modelo and modelo.conteudo:
            texto = modelo.conteudo
            texto = texto.replace("{{ cliente.nome }}", nome).replace("{{ cliente.documento }}", documento).replace("{{ cliente.endereco_completo }}", endereco)
            texto = re.sub(r"\{\{\s*cliente\.(nome|documento|endereco_completo)\s*\}\}", "", texto)
    except Exception:
        pass

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2.5 * cm, leftMargin=2.5 * cm, topMargin=2.5 * cm, bottomMargin=2.5 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DeclarationTitle", parent=styles["Title"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=2 * cm)
    body_style = ParagraphStyle("DeclarationBody", parent=styles["BodyText"], alignment=TA_JUSTIFY, fontSize=12, leading=22, spaceAfter=1 * cm)
    footer_style = ParagraphStyle("DeclarationFooter", parent=styles["BodyText"], alignment=TA_CENTER, fontSize=11, leading=16)
    story = [Paragraph(titulo, title_style), Paragraph(texto, body_style), Spacer(1, 2.5 * cm), Paragraph(f"Local e data: ____________________, {hoje}.", body_style), Spacer(1, 2.5 * cm), Paragraph("________________________________________<br/>Assinatura do(a) declarante", footer_style)]
    doc.build(story)
    return buffer.getvalue()
