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
from reportlab.lib.pagesizes import A4, landscape
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


def _draw_fitted_image(
    pdf: canvas.Canvas,
    image_data: bytes,
    image_size: tuple[int, int],
    box: tuple[float, float, float, float],
) -> None:
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


def montar_ficha_legivel(documentos: Iterable[tuple[str, bytes, str]]) -> bytes:
    """Gera um PDF único, com cada página-fonte em uma página A4 legível."""
    documentos = list(documentos)
    tipos_esperados = ["CNH", "CR", "CRAF"]
    if [item[0] for item in documentos] != tipos_esperados:
        raise FichaCompactaError("A seleção deve conter uma CNH, um CR e um CRAF, nessa ordem.")

    rendered_groups: list[tuple[str, list[tuple[bytes, int, int]]]] = []
    for tipo, data, _filename in documentos:
        rendered_groups.append((tipo, _render_document(data)))

    total_pages = sum(len(pages) for _tipo, pages in rendered_groups)
    if not total_pages:
        raise FichaCompactaError("Nenhuma página válida foi encontrada nos documentos selecionados.")

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    pdf.setTitle("Documentos para conferência e envio ao TD")
    pdf.setAuthor("M4 Tática")

    page_number = 0
    for tipo, pages in rendered_groups:
        for index, (page_image, image_width, image_height) in enumerate(pages, start=1):
            page_size = landscape(A4) if image_width > image_height else A4
            page_width, page_height = page_size
            pdf.setPageSize(page_size)

            margin = 14
            header_height = 26
            footer_height = 18
            pdf.setFillColor(HexColor("#18324b"))
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(margin, page_height - margin - 12, f"{tipo} — página {index} de {len(pages)}")
            pdf.setFillColor(HexColor("#59636e"))
            pdf.setFont("Helvetica", 7)
            pdf.drawRightString(page_width - margin, page_height - margin - 12, date.today().strftime("%d/%m/%Y"))
            pdf.setStrokeColor(HexColor("#e1e6ea"))
            pdf.line(margin, page_height - margin - header_height, page_width - margin, page_height - margin - header_height)

            image_box = (
                margin,
                margin + footer_height,
                page_width - 2 * margin,
                page_height - 2 * margin - header_height - footer_height,
            )
            _draw_fitted_image(pdf, page_image, (image_width, image_height), image_box)

            page_number += 1
            pdf.setFont("Helvetica", 6)
            pdf.drawCentredString(
                page_width / 2,
                margin + 5,
                f"Cópia para conferência; mantenha os originais no cadastro.  Página {page_number} de {total_pages}.",
            )
            if page_number < total_pages:
                pdf.showPage()

    pdf.save()
    return output.getvalue()


def montar_ficha_compacta(documentos: Iterable[tuple[str, bytes, str]]) -> bytes:
    """Monta CNH, CR e CRAF em três colunas numa página A4 horizontal, sem OCR ou rede."""
    documentos = list(documentos)
    tipos_esperados = ["CNH", "CR", "CRAF"]
    if [item[0] for item in documentos] != tipos_esperados:
        raise FichaCompactaError("A seleção deve conter uma CNH, um CR e um CRAF, nessa ordem.")

    rendered_groups: list[tuple[str, list[tuple[bytes, int, int]]]] = []
    for tipo, data, _filename in documentos:
        rendered_groups.append((tipo, _render_document(data)))

    page_width, page_height = landscape(A4)
    margin = 14
    top_reserved = 34
    bottom_reserved = 18
    column_gap = 8
    content_width = page_width - (2 * margin)
    column_width = (content_width - (2 * column_gap)) / 3
    content_top = page_height - margin - top_reserved
    content_bottom = margin + bottom_reserved
    content_height = content_top - content_bottom

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=landscape(A4), pageCompression=1)
    pdf.setTitle("Ficha compacta de documentos")
    pdf.setAuthor("M4 Tática")

    pdf.setFillColor(HexColor("#18324b"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin, page_height - margin - 12, "FICHA COMPACTA DE DOCUMENTOS")
    pdf.setFillColor(HexColor("#59636e"))
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(page_width - margin, page_height - margin - 12, date.today().strftime("%d/%m/%Y"))

    for column_index, (tipo, pages) in enumerate(rendered_groups):
        column_x = margin + column_index * (column_width + column_gap)
        label_height = 18
        image_top = content_top - label_height - 4
        image_bottom = content_bottom + 5
        image_area_height = image_top - image_bottom
        page_gap = 5
        tile_height = (image_area_height - (len(pages) - 1) * page_gap) / len(pages)

        pdf.setStrokeColor(HexColor("#b9c3cc"))
        pdf.setLineWidth(0.55)
        pdf.roundRect(column_x, content_bottom, column_width, content_height, 3, stroke=1, fill=0)
        pdf.setFillColor(HexColor("#18324b"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(column_x + 6, content_top - 12, tipo)
        pdf.setStrokeColor(HexColor("#e1e6ea"))
        pdf.line(column_x + 5, content_top - label_height, column_x + column_width - 5, content_top - label_height)

        for page_index, (page_image, image_width, image_height_px) in enumerate(pages):
            tile_top = image_top - page_index * (tile_height + page_gap)
            tile_bottom = tile_top - tile_height
            box = (column_x + 5, tile_bottom, column_width - 10, tile_height)
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
