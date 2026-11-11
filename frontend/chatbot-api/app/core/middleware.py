import logging
import time
import uuid

from starlette.responses import JSONResponse


class SecurityMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        status_code = 500
        started = time.perf_counter()

        async def secure_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers += [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                ]
                if self.settings.environment == "production":
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                message["headers"] = headers
            await send(message)

        try:
            # Read bounded request body before routing; protects chunked as well as Content-Length requests.
            chunks = []
            size = 0
            while True:
                part = await receive()
                if part["type"] == "http.disconnect":
                    status_code = 499
                    return
                size += len(part.get("body", b""))
                if size > self.settings.max_body_bytes:
                    return await JSONResponse(
                        {"detail": "Nội dung yêu cầu quá lớn."}, 413
                    )(scope, receive, secure_send)
                chunks.append(part.get("body", b""))
                if not part.get("more_body", False):
                    break
            sent = False

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {
                        "type": "http.request",
                        "body": b"".join(chunks),
                        "more_body": False,
                    }
                return await receive()

            await self.app(scope, replay, secure_send)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            level = (
                logging.ERROR
                if status_code >= 500
                else logging.WARNING
                if status_code >= 400
                else logging.INFO
            )
            logging.getLogger("chatbot.access").log(
                level,
                "%s %s status=%d duration_ms=%.2f request_id=%s",
                scope.get("method", "UNKNOWN"),
                scope.get("path", "/"),
                status_code,
                elapsed_ms,
                request_id,
            )
