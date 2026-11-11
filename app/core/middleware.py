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


class RequestSizeLimitMiddleware:
    """Bound request bodies, including streamed requests without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int, upload_max_bytes: int = 16777216) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.upload_max_bytes = upload_max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        path = scope.get("path", "")
        limit = (
            self.upload_max_bytes
            if path in {
                "/v1/admin/sources",
                "/v1/admin/packages/inspect",
                "/v1/admin/packages/inspect-upload",
                "/v1/admin/releases",
                "/v1/admin/releases/upload",
                "/v1/admin/chat-preview",
            }
            or path.startswith("/v1/admin/modules/")
            else self.max_bytes
        )
        while True:
            event = await receive()
            if event["type"] != "http.request":
                return
            chunk = event.get("body", b"")
            size += len(chunk)
            if size > limit:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send({"type": "http.response.body", "body": b"Request too large"})
                return
            chunks.append(chunk)
            if not event.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
