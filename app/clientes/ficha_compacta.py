"""Geração local de uma ficha A4 compacta a partir dos arquivos originais.

O resultado é uma cópia derivada de consulta/envio; nunca altera os arquivos-fonte.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Iterable
import warnings

from PIL import Image, ImageOps
import pypdfium2 as pdfium
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MAX_SOURCE_BYTES = 15 * 1024 * 1024
MAX_DOCUMENT_PAGES = 2
MAX_IMAGE_PIXELS = 30_000_000
MAX_IMAGE_SIDE = 5000
PDF_RENDER_SCALE = 2.4


class FichaCompactaError(ValueError):
    """Erro esperado de formato ou limite ao montar a ficha compacta."""


def _jpeg_bytes(image: Image.Image) -> tuple[bytes, int, int]:
    image = image.convert("RGB")
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    width, height = image.size
    image.close()
    return output.getvalue(), width, height


def _render_pdf(data: bytes) -> list[tuple[bytes, int, int]]:
    try:
        document = pdfium.PdfDocument(data)
    except Exception as exc:
        raise FichaCompactaError("Não foi possível abrir um dos PDFs selecionados.") from exc

    rendered: list[tuple[bytes, int, int]] = []
    try:
        page_count = len(document)
        if not 1 <= page_count <= MAX_DOCUMENT_PAGES:
            raise FichaCompactaError(
                "Cada arquivo pode ter no máximo 2 páginas para caber integralmente na ficha."
            )

        for index in range(page_count):
            page = document[index]
            try:
                page_width, page_height = page.get_size()
                if (
                    page_width <= 0
                    or page_height <= 0
                    or page_width > 1800
                    or page_height > 1800
                    or page_width * page_height > 1_800_000
                ):
                    raise FichaCompactaError("Um dos PDFs tem dimensões de página fora do limite seguro.")

                bitmap = page.render(scale=PDF_RENDER_SCALE)
                try:
                    image = bitmap.to_pil()
                    rendered.append(_jpeg_bytes(image))
                finally:
                    bitmap.close()
            finally:
                page.close()
    finally:
        document.close()

    return rendered


def _render_image(data: bytes) -> list[tuple[bytes, int, int]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(BytesIO(data))
            if source.format not in {"JPEG", "PNG"}:
                source.close()
                raise FichaCompactaError("Use arquivos PDF, JPG ou PNG.")
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                source.close()
                raise FichaCompactaError("Uma das imagens excede o limite seguro de resolução.")
            image = ImageOps.exif_transpose(source).convert("RGB")
            source.close()
            return [_jpeg_bytes(image)]
    except FichaCompactaError:
        raise
    except Exception as exc:
        raise FichaCompactaError("Não foi possível abrir uma das imagens selecionadas.") from exc


def _render_document(data: bytes) -> list[tuple[bytes, int, int]]:
    if not data:
        raise FichaCompactaError("Um dos documentos está vazio.")
    if len(data) > MAX_SOURCE_BYTES:
        raise FichaCompactaError("Cada arquivo selecionado deve ter até 15 MB.")

    if b"%PDF-" in data[:1024]:
        return _render_pdf(data)
    if data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _render_image(data)
    raise FichaCompactaError("Um dos arquivos não é um PDF, JPG ou PNG válido.")


def _draw_fitted_image(pdf: canvas.Canvas, image_data: bytes, image_size: tuple[int, int], box: tuple[float, float, float, float]) -> None:
    x, y, box_width, box_height = box
    image_width, image_height = image_size
    scale = min(box_width / image_width, box_height / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    draw_x = x + (box_width - draw_width) / 2
    draw_y = y + (box_height - draw_height) / 2
    pdf.drawImage(
        ImageReader(BytesIO(image_data)),
        draw_x,
        draw_y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )


def montar_ficha_compacta(documentos: Iterable[tuple[str, bytes, str]]) -> bytes:
    """Monta CNH, CR e CRAF em três faixas numa página A4, sem OCR ou rede."""
    documentos = list(documentos)
    tipos_esperados = ["CNH", "CR", "CRAF"]
    if [item[0] for item in documentos] != tipos_esperados:
        raise FichaCompactaError("A seleção deve conter uma CNH, um CR e um CRAF, nessa ordem.")

    rendered_groups: list[tuple[str, list[tuple[bytes, int, int]]]] = []
    for tipo, data, _filename in documentos:
        rendered_groups.append((tipo, _render_document(data)))

    page_width, page_height = A4
    margin = 16
    top_reserved = 38
    bottom_reserved = 18
    row_gap = 7
    content_width = page_width - (2 * margin)
    content_top = page_height - margin - top_reserved
    content_bottom = margin + bottom_reserved
    row_height = (content_top - content_bottom - (2 * row_gap)) / 3

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    pdf.setTitle("Ficha compacta de documentos")
    pdf.setAuthor("M4 Tática")

    pdf.setFillColor(HexColor("#18324b"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin, page_height - margin - 12, "FICHA COMPACTA DE DOCUMENTOS")
    pdf.setFillColor(HexColor("#59636e"))
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(page_width - margin, page_height - margin - 12, date.today().strftime("%d/%m/%Y"))

    for row_index, (tipo, pages) in enumerate(rendered_groups):
        row_top = content_top - row_index * (row_height + row_gap)
        row_bottom = row_top - row_height
        label_height = 15
        image_bottom = row_bottom + 5
        image_top = row_top - label_height - 3
        image_height = image_top - image_bottom

        pdf.setStrokeColor(HexColor("#b9c3cc"))
        pdf.setLineWidth(0.55)
        pdf.roundRect(margin, row_bottom, content_width, row_height, 3, stroke=1, fill=0)
        pdf.setFillColor(HexColor("#18324b"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(margin + 6, row_top - 11, tipo)
        pdf.setStrokeColor(HexColor("#e1e6ea"))
        pdf.line(margin + 5, row_top - label_height, page_width - margin - 5, row_top - label_height)

        if len(pages) == 1:
            boxes = [(margin + 5, image_bottom, content_width - 10, image_height)]
        else:
            column_gap = 6
            column_width = (content_width - 10 - column_gap) / 2
            boxes = [
                (margin + 5, image_bottom, column_width, image_height),
                (margin + 5 + column_width + column_gap, image_bottom, column_width, image_height),
            ]

        for page_image, image_width, image_height_px in pages:
            box = boxes.pop(0)
            _draw_fitted_image(pdf, page_image, (image_width, image_height_px), box)

    pdf.setFillColor(HexColor("#59636e"))
    pdf.setFont("Helvetica", 6)
    pdf.drawCentredString(
        page_width / 2,
        margin + 5,
        "Cópia compacta para conferência/envio. Mantenha os documentos originais no cadastro.",
    )
    pdf.showPage()
    pdf.save()
    return output.getvalue()
