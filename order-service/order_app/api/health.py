import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from order_app.database import get_db
from order_app.clients.catalog_client import catalog_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health & Probes"])


@router.get("/health/live", summary="Liveness probe")
@router.get("/api/orders/health/live", summary="Liveness probe (prefixed)")
def liveness():
    """
    Kubernetes liveness probe.
    Must not fail merely because downstream dependencies (e.g. database, catalog service) are unavailable.
    """
    return {"status": "UP", "service": "order-service"}


@router.get("/health/ready", summary="Readiness probe")
@router.get("/api/orders/health/ready", summary="Readiness probe (prefixed)")
def readiness(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe.
    Checks DB connectivity and downstream catalog service reachability.
    """
    checks = {
        "database": "UNKNOWN",
        "catalog_service": "UNKNOWN"
    }

    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "CONNECTED"
        db_ok = True
    except Exception as e:
        logger.error(f"Order database check failed: {e}")
        checks["database"] = "UNAVAILABLE"

    catalog_ok = catalog_client.check_health()
    checks["catalog_service"] = "REACHABLE" if catalog_ok else "UNREACHABLE"

    if db_ok and catalog_ok:
        return {"status": "UP", "checks": checks}
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=status_code, content={"status": "DOWN", "checks": checks})
