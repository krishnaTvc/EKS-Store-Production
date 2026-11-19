# Multi-stage Dockerfile for catalog-service
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime image
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 1000 -m appuser

COPY --from=builder /install /usr/local
COPY alembic.ini .
COPY alembic/ alembic/
COPY catalog_app/ catalog_app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8001

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8001/health/live || exit 1

CMD ["uvicorn", "catalog_app.main:app", "--host", "0.0.0.0", "--port", "8001"]

