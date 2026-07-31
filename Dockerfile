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

# App source (includes README.md at /app/README.md for in-image docs)
COPY README.md .
COPY . .

RUN mkdir -p uploads/products \
    && test -f /app/README.md

EXPOSE 8908

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8908"]
