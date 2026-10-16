from __future__ import annotations

import html
import io
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


MODELOS_PADRAO = [
    (
        "Declaração de Residência",
        "declaracao_residencia",
        (
            "Eu, <b>{{ proprietario.nome }}</b>, inscrito(a) no CPF sob o nº "
            "<b>{{ proprietario.documento }}</b> e portador(a) do RG nº "
            "<b>{{ proprietario.rg }}</b> <b>{{ proprietario.rg_emissor }}</b>, "
            "residente e domiciliado(a) no endereço <b>{{ proprietario.endereco_completo }}</b>,"
            "<br/><br/>"
            "DECLARO, sob as penas da lei e junto à Polícia Federal (SINARM), que o(a) Sr.(a) "
            "<b>{{ cliente.nome }}</b>, inscrito(a) no CPF sob o nº <b>{{ cliente.documento }}</b>, "
            "reside de forma fixa e permanente no endereço <b>{{ cliente.endereco_completo }}</b>."
            "<br/><br/>"
            "Declaro, ainda, que o vínculo que possuo com o requerente é o de "
            "<b>{{ declaracao.vinculo }}</b>."
            "<br/><br/>"
            "Por ser a expressão da verdade e ciente das responsabilidades civis e penais "
            "decorrentes de declaração falsa, firmo a presente."
        ),
    ),
    (
        "Declaração de Inexistência de Inquéritos Policiais ou Processos Criminais",
        "declaracao_nao_inquerito",
        (
            "Eu, <b>{{ cliente.nome }}</b>, CPF: <b>{{ cliente.documento }}</b>, residindo em "
            "<b>{{ cliente.endereco_completo }}</b>, declaro, sob as penas da lei, que não "
            "respondo processo criminal e/ou inquérito policial, tanto no Estado de domicílio "
            "quanto nos demais entes federativos, e estou ciente de que, em caso de falsidade "
            "ideológica, ficarei sujeito às sanções prescritas no Código Penal e às demais "
            "cominações legais aplicáveis."
            "<br/><br/>"
            "<i>“Art. 299 —<br/><br/>"
            "Omitir, em documento público ou particular, declaração que nele deveria constar, "
            "ou ele inserir ou fazer inserir declaração falsa ou diversa da que devia ser escrita, "
            "com o fim de prejudicar direito, criar obrigação ou alterar a verdade sobre o fato "
            "juridicamente relevante. Pena: reclusão de 1 (um) a 5 (cinco) anos e multa, se o "
            "documento é público e reclusão de 1 (um) a 3 (três) anos, se o documento é particular.”</i>"
        ),
    ),
]

_MODELOS_POR_CHAVE = {chave: (titulo, conteudo) for titulo, chave, conteudo in MODELOS_PADRAO}
_TIPO_PARA_CHAVE = {
    "residencia": "declaracao_residencia",
    "nao_inquerito": "declaracao_nao_inquerito",
}
_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def endereco_completo_cliente(cliente) -> str:
    endereco = next((item for item in (cliente.enderecos or []) if item.tipo == "residencial"), None)
    if not endereco:
        return ""
    partes = [
        endereco.logradouro,
        endereco.numero,
        endereco.complemento,
        endereco.bairro,
        endereco.cidade,
        endereco.estado,
        endereco.cep,
    ]
    return ", ".join(str(item).strip() for item in partes if item and str(item).strip())


def localidade_cliente(cliente) -> str:
    endereco = next((item for item in (cliente.enderecos or []) if item.tipo == "residencial"), None)
    if not endereco:
        return ""
    cidade = str(endereco.cidade or "").strip()
    estado = str(endereco.estado or "").strip()
    if cidade and estado:
        return f"{cidade}/{estado}"
    return cidade or estado


def _texto_seguro(valor, fallback: str) -> str:
    texto = str(valor or "").strip()
    return html.escape(texto or fallback, quote=True)


def formatar_cpf(valor) -> str:
    """Formata CPFs com 11 dígitos, mantendo outros documentos como foram informados."""
    original = str(valor or "").strip()
    digitos = re.sub(r"\D", "", original)
    if len(digitos) != 11:
        return original
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def _data_extenso(data: date) -> str:
    dia = "1º" if data.day == 1 else str(data.day)
    mes = _MESES[data.month - 1].capitalize()
    return f"{dia} de {mes} de {data.year}"


def _local_data(local: str, data: date) -> str:
    local_limpo = str(local or "").strip() or "________________________"
    return f"{html.escape(local_limpo, quote=True)}, {_data_extenso(data)}."


def _substituir_variaveis(conteudo: str, valores: dict[str, str]) -> str:
    return _TOKEN_RE.sub(lambda match: valores.get(match.group(1), ""), conteudo or "")


def gerar_declaracao(cliente, tipo: str, dados: dict | None = None, data_emissao: date | None = None) -> bytes:
    chave_modelo = _TIPO_PARA_CHAVE.get(tipo)
    if not chave_modelo:
        raise ValueError("Tipo de declaração inválido.")

    dados = dados or {}
    titulo, texto_padrao = _MODELOS_POR_CHAVE[chave_modelo]
    modelo = None
    try:
        from app.models import ModeloDocumento

        modelo = ModeloDocumento.query.filter_by(chave=chave_modelo).first()
    except Exception:
        # A função ainda gera um modelo padrão se não estiver dentro do app context.
        modelo = None

    if modelo:
        titulo = modelo.titulo or titulo
        texto_padrao = modelo.conteudo or texto_padrao

    endereco_cliente = (
        str(dados.get("cliente_endereco") or "").strip()
        or endereco_completo_cliente(cliente)
    )
    valores = {
        "cliente.nome": _texto_seguro(cliente.nome, "________________________________________"),
        "cliente.documento": _texto_seguro(formatar_cpf(cliente.documento), "________________________"),
        "cliente.endereco_completo": _texto_seguro(endereco_cliente, "________________________________________"),
        "proprietario.nome": _texto_seguro(dados.get("proprietario_nome"), "________________________"),
        "proprietario.documento": _texto_seguro(
            formatar_cpf(dados.get("proprietario_documento")), "________________________"
        ),
        "proprietario.rg": _texto_seguro(dados.get("proprietario_rg"), "________________________"),
        "proprietario.rg_emissor": _texto_seguro(dados.get("proprietario_rg_emissor"), "________"),
        "proprietario.endereco_completo": _texto_seguro(
            dados.get("proprietario_endereco"), "________________________________________"
        ),
        "declaracao.vinculo": _texto_seguro(dados.get("vinculo"), "________________________"),
    }
    texto = _substituir_variaveis(texto_padrao, valores)

    if data_emissao is None:
        data_emissao = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    local = dados.get("local") or localidade_cliente(cliente)
    assinatura_nome = valores["proprietario.nome"] if tipo == "residencia" else valores["cliente.nome"]
    assinatura_documento = valores["proprietario.documento"] if tipo == "residencia" else valores["cliente.documento"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=titulo,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DeclarationTitle", parent=styles["Title"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=13, leading=17, spaceAfter=0.3 * cm,
    )
    subtitle_style = ParagraphStyle(
        "DeclarationSubtitle", parent=styles["BodyText"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=11, leading=14, spaceAfter=1.2 * cm,
    )
    body_style = ParagraphStyle(
        "DeclarationBody", parent=styles["BodyText"], alignment=TA_JUSTIFY,
        fontSize=11, leading=17, spaceAfter=0.35 * cm,
    )
    footer_style = ParagraphStyle(
        "DeclarationFooter", parent=styles["BodyText"], alignment=TA_CENTER,
        fontSize=10.5, leading=15,
    )
    signature_style = ParagraphStyle(
        "DeclarationSignature", parent=styles["BodyText"], alignment=TA_CENTER,
        fontSize=10.5, leading=14,
    )

    story = [Paragraph(html.escape(str(titulo)).upper(), title_style)]
    if tipo == "residencia":
        story.extend([
            Paragraph("(Imóvel de Terceiro/Familiar)", subtitle_style),
            Paragraph(texto, body_style),
        ])
    else:
        story.extend([Paragraph(texto, body_style)])

    story.extend([
        Spacer(1, 0.5 * cm),
        Paragraph(_local_data(local, data_emissao), footer_style),
        Spacer(1, 1.4 * cm),
        Paragraph("________________________________________", signature_style),
        Paragraph(f"<b>{assinatura_nome}</b><br/>CPF: {assinatura_documento}", signature_style),
    ])
    doc.build(story)
    return buffer.getvalue()
