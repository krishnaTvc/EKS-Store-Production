# Multi-stage Dockerfile for order-service
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
    ca-certificates \
    curl \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 1000 -m appuser

COPY --from=builder /install /usr/local
COPY alembic.ini .
COPY alembic/ alembic/
COPY order_app/ order_app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8002

RUN mkdir -p /app/certs && curl --fail --silent --show-error --location \
    https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
    -o /app/certs/rds-ca.pem
ENV PGSSLROOTCERT=/app/certs/rds-ca.pem

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8002/health/live || exit 1

CMD ["uvicorn", "order_app.main:app", "--host", "0.0.0.0", "--port", "8002"]

