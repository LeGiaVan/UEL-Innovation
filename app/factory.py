from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware


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
        description="PoC API for the UEL RAG virtual assistant.",
        docs_url="/docs" if runtime_settings.app_env != "uat" else None,
        lifespan=lifespan,
        redoc_url=None,
        title=runtime_settings.app_name,
        version="0.1.0",
    )
    app.add_middleware(
        RequestContextMiddleware,
        header_name=runtime_settings.request_id_header,
    )
    app.include_router(health_router)
    return app
