import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from catalog_app.config import settings
from catalog_app.middleware.correlation import CorrelationIdMiddleware, CorrelationIdFilter
from catalog_app.middleware.metrics import PrometheusMiddleware, metrics_endpoint
from catalog_app.api import items, categories, health

# Structured Logging Setup
logging_format = "%(asctime)s [%(levelname)s] [corr_id=%(correlation_id)s] %(name)s: %(message)s"
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(logging_format))
handler.addFilter(CorrelationIdFilter())

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO), handlers=[handler])
logger = logging.getLogger("catalog-service")

app = FastAPI(
    title="EKS Beverage Store - Catalog Service",
    description="Microservice providing beverage catalog data, search, filtering, and image resolution for Amazon EKS demo.",
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

# Mount local assets for development mode
assets_dir = settings.LOCAL_ASSETS_DIR
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    logger.info(f"Mounted local static assets directory at /assets -> {assets_dir}")

# Routers
app.include_router(health.router)
app.include_router(items.router)
app.include_router(categories.router)

# Metrics endpoint
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], tags=["Observability"])


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "catalog-service",
        "status": "UP",
        "docs_url": "/docs",
        "health_live": "/health/live",
        "health_ready": "/health/ready",
        "metrics": "/metrics"
    }
