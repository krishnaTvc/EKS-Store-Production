import uuid
import logging
import httpx
from fastapi import HTTPException, status

from order_app.config import settings
from order_app.middleware.correlation import correlation_id_ctx

logger = logging.getLogger(__name__)


class CatalogClientError(Exception):
    pass


class CatalogClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.CATALOG_SERVICE_URL).rstrip("/")
        self.timeout = timeout or settings.CATALOG_TIMEOUT_SECONDS

    def get_catalog_item(self, item_id: uuid.UUID) -> dict:
        url = f"{self.base_url}/api/catalog/items/{item_id}"
        headers = {}
        corr_id = correlation_id_ctx.get()
        if corr_id:
            headers["X-Correlation-Id"] = corr_id

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)

                if resp.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Catalog item '{item_id}' not found in catalog"
                    )

                if resp.status_code != 200:
                    logger.error(f"Catalog service returned status {resp.status_code}: {resp.text}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Downstream catalog service error (status {resp.status_code})"
                    )

                item_data = resp.json()
                if not item_data.get("active", True):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Catalog item '{item_id}' ({item_data.get('product_name')}) is currently inactive and cannot be ordered"
                    )

                return item_data

        except httpx.TimeoutException:
            logger.error(f"Catalog service timed out after {self.timeout}s calling {url}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Catalog service timed out while retrieving product details"
            )
        except httpx.RequestError as e:
            logger.error(f"Catalog service unreachable at {url}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Catalog service is currently unavailable"
            )

    def check_health(self) -> bool:
        """Quick ping for readiness checks."""
        url = f"{self.base_url}/health/live"
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(url)
                return resp.status_code == 200
        except Exception:
            return False


catalog_client = CatalogClient()
