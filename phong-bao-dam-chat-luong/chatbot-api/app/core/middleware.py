from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.origins import allowed_origins, origin_allowed, origin_from_headers

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


class OriginGuardMiddleware:
    """Chặn POST/PUT/DELETE /api khi thiếu Origin hoặc Origin lạ. Không bọc body — SSE chat vẫn chạy."""

    def __init__(self, app: ASGIApp, fastapi_app: ASGIApp | None = None) -> None:
        self.app = app
        self.fastapi_app = fastapi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method") or ""
        path = scope.get("path") or ""
        if method not in MUTATING or not path.startswith("/api"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        host_app = self.fastapi_app
        settings = getattr(getattr(host_app, "state", None), "settings", None)
        department = getattr(getattr(host_app, "state", None), "department", None) or {}
        allowed = allowed_origins(settings, department)
        origin = origin_from_headers(
            request.headers.get("origin") or "",
            request.headers.get("referer") or "",
        )
        if origin_allowed(origin, allowed):
            await self.app(scope, receive, send)
            return
        response = JSONResponse({"detail": "Origin không hợp lệ"}, status_code=403)
        await response(scope, receive, send)
