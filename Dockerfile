FROM python:3.13-slim

LABEL org.opencontainers.image.title="ShopSphere" \
      org.opencontainers.image.description="Amazon/Flipkart-style e-commerce platform (FastAPI)" \
      org.opencontainers.image.source="https://github.com/sharanyashwant27-tech/E-commerce-Platform-Python" \
      org.opencontainers.image.documentation="https://github.com/sharanyashwant27-tech/E-commerce-Platform-Python/blob/main/README.md" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Bake README first so /app/README.md is always present for in-image docs,
# then copy the full application (static product photos, templates, API, etc.).
COPY README.md /app/README.md
COPY . .

RUN mkdir -p uploads/products uploads/invoices \
    && test -f /app/README.md \
    && test -s /app/README.md \
    && ls /app/static/images/*.jpg >/dev/null 2>&1 \
    && echo "ShopSphere image OK — README.md and product photos included"

EXPOSE 8908

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8908"]
