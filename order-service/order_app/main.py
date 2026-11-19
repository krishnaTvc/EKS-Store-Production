import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from order_app.config import settings
from order_app.middleware.correlation import CorrelationIdMiddleware, CorrelationIdFilter
from order_app.middleware.metrics import PrometheusMiddleware, metrics_endpoint
from order_app.api import orders, health

# Structured Logging Setup
logging_format = "%(asctime)s [%(levelname)s] [corr_id=%(correlation_id)s] %(name)s: %(message)s"
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(logging_format))
handler.addFilter(CorrelationIdFilter())

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO), handlers=[handler])
logger = logging.getLogger("order-service")

app = FastAPI(
    title="EKS Beverage Store - Order Service",
    description="Microservice managing beverage orders, item price snapshotting, and robust idempotency.",
    version="1.0.0"
)

# Middlewares
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(PrometheusMiddleware)

if settings.CORS_ORIGINS:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
elif settings.APP_ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:80", "http://127.0.0.1:80"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routers
app.include_router(health.router)
app.include_router(orders.router)

# Metrics endpoint
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], tags=["Observability"])


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "order-service",
        "status": "UP",
        "docs_url": "/docs",
        "health_live": "/health/live",
        "health_ready": "/health/ready",
        "metrics": "/metrics"
    }
