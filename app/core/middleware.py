import re
import time
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from structlog.contextvars import bind_contextvars, clear_contextvars

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a safe request ID and emit one structured completion log per request."""

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        clear_contextvars()
        incoming_request_id = request.headers.get(self.header_name, "")
        request_id = (
            incoming_request_id
            if _REQUEST_ID_PATTERN.fullmatch(incoming_request_id)
            else str(uuid4())
        )
        bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            await logger.aexception(
                "request_failed",
                method=request.method,
                path=request.url.path,
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers[self.header_name] = request_id
        await logger.ainfo(
            "request_completed",
            duration_ms=duration_ms,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        clear_contextvars()
        return response
