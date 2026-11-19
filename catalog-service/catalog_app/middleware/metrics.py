import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "catalog_http_requests_total",
    "Total HTTP requests to catalog-service",
    ["method", "endpoint", "status"]
)

REQUEST_DURATION = Histogram(
    "catalog_http_request_duration_seconds",
    "HTTP request duration in seconds for catalog-service",
    ["method", "endpoint"]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Ignore prometheus scrape requests in request metrics
        if request.url.path in ("/metrics", "/health/live", "/health/ready"):
            return await call_next(request)

        start_time = time.time()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_COUNT.labels(method=method, endpoint=path, status=status).inc()
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)

        return response


def metrics_endpoint():
    """Generates Prometheus format metric payload."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
