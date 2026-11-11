import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import router
from app.core.config import Settings
from app.core.middleware import SecurityMiddleware
from app.db.factory import create_database
from app.services.providers import StubAnswerProvider
from app.services.rag import RagAnswerProvider


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    db = create_database(settings)

    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        logging.getLogger("chatbot").info(
            "Backend started with %s storage", settings.database_backend
        )
        try:
            yield
        finally:
            db.close()

    app = FastAPI(
        title="UEL Department Chatbot API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )
    provider = (
        RagAnswerProvider(settings) if settings.provider == "rag" else StubAnswerProvider()
    )
    app.state.db, app.state.settings, app.state.provider = db, settings, provider
    app.include_router(router)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Department-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        # Pydantic's raw errors may echo passwords or message content in `input`.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ]
            },
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc):
        logging.getLogger("chatbot").error(
            "Unhandled backend error: %s request_id=%s",
            type(exc).__name__,
            getattr(request.state, "request_id", "unknown"),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Lỗi xử lý nội bộ."},
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/health/live", tags=["Health"])
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"])
    def ready():
        db.ping()
        return {
            "status": "ready",
            "provider": "stub",
            "database": settings.database_backend,
        }

    return app


app = create_app()
