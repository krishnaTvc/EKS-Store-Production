import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from catalog_app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health & Probes"])


@router.get("/health/live", summary="Liveness probe")
@router.get("/api/catalog/health/live", summary="Liveness probe (prefixed)")
def liveness():
    """
    Kubernetes liveness probe.
    Must not fail merely because downstream dependencies (e.g. database) are unavailable.
    """
    return {"status": "UP", "service": "catalog-service"}


@router.get("/health/ready", summary="Readiness probe")
@router.get("/api/catalog/health/ready", summary="Readiness probe (prefixed)")
def readiness(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe.
    Checks that the database connection is operational and ready to serve traffic.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "UP", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "DOWN", "database": "UNAVAILABLE", "error": "Database check failed"}
        )
