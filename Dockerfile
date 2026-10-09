FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    POPPLER_PATH=/usr/bin

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        passwd \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/* \
    && command -v pdfinfo \
    && command -v pdftoppm \
    && tesseract --list-langs 2>/dev/null | grep -Fqx eng \
    && tesseract --list-langs 2>/dev/null | grep -Fqx por

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN useradd --system --create-home --user-group --uid 10001 app \
    && mkdir -p /app/logs /app/uploads /app/instance \
    && chown app:app /app/logs /app/uploads /app/instance

USER app
ENV HOME=/home/app

# Mantém o mesmo WSGI alvo usado atualmente pelo serviço Render.
CMD ["gunicorn", "--timeout", "120", "run:app"]
