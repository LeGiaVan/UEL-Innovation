from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.routes.admin import router as admin_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, RequestSizeLimitMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    logger = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = runtime_settings
        app.state.engine = create_async_engine(
            runtime_settings.postgres_url,
            pool_pre_ping=True,
        )
        app.state.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=runtime_settings.readiness_timeout_seconds,
        )
        await logger.ainfo(
            "application_started",
            app_env=runtime_settings.app_env,
            department_id=runtime_settings.app_department_id,
            module_code=runtime_settings.app_module_code,
        )
        try:
            yield
        finally:
            await app.state.http_client.aclose()
            await app.state.engine.dispose()
            await logger.ainfo("application_stopped")

    app = FastAPI(
        description=(
            "UEL RAG assistant. Chat uses X-API-Key. "
            "Adding a department: POST /v1/admin/packages/inspect (fingerprint the three "
            "standard XLSX templates) then POST /v1/admin/releases (registry + Bronze/Silver/"
            "Qdrant). dry_run=true validates; dry_run=false writes MinIO, PostgreSQL and Qdrant. "
            "Admin uses X-Admin-Key. New modules following Template 1/2/3 need no code change."
        ),
        docs_url="/docs" if runtime_settings.app_env != "uat" else None,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "health", "description": "Liveness and dependency readiness."},
            {
                "name": "chat",
                "description": (
                    "Tenant-scoped chat. POST /v1/chat returns JSON; "
                    "POST /v1/chat/stream is SSE (status, token, done)."
                ),
            },
            {
                "name": "administration",
                "description": (
                    "Registry and ETL. Inspect templates → ingest release → Bronze snapshot, "
                    "Silver policy/FAQ/docs, Gold vectors in Qdrant."
                ),
            },
        ],
        redoc_url=None,
        title=runtime_settings.app_name,
        version="0.1.0",
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=runtime_settings.request_max_bytes,
        upload_max_bytes=runtime_settings.source_upload_max_bytes,
    )
    app.add_middleware(
        RequestContextMiddleware,
        header_name=runtime_settings.request_id_header,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_methods=["POST", "GET", "PUT"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID", "X-Admin-Key", "If-Match"],
        expose_headers=["ETag", runtime_settings.request_id_header],
    )
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(admin_router)

    @app.get("/", include_in_schema=False)
    async def web_chat() -> FileResponse:
        return FileResponse(Path(__file__).parent / "web" / "index.html")

    @app.get("/admin", include_in_schema=False)
    async def web_admin() -> FileResponse:
        return FileResponse(Path(__file__).parent / "web" / "admin.html")

    return app
