import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        corr_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        correlation_id_ctx.set(corr_id)

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects correlation_id into all log records."""
    def filter(self, record):
        record.correlation_id = correlation_id_ctx.get() or "no-corr-id"
        return True
