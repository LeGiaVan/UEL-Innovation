import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings

DependencyState = Literal["ok", "error"]


async def _check_postgres(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_http(client: httpx.AsyncClient, url: str) -> None:
    response = await client.get(url)
    response.raise_for_status()


async def _run_check(
    check: Callable[[], Awaitable[None]],
    timeout_seconds: float,
) -> DependencyState:
    try:
        async with asyncio.timeout(timeout_seconds):
            await check()
    except (TimeoutError, OSError, httpx.HTTPError, SQLAlchemyError):
        return "error"
    return "ok"


async def check_dependencies(
    engine: AsyncEngine,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> dict[str, DependencyState]:
    postgres, qdrant, minio = await asyncio.gather(
        _run_check(
            lambda: _check_postgres(engine),
            settings.readiness_timeout_seconds,
        ),
        _run_check(
            lambda: _check_http(http_client, settings.qdrant_ready_url),
            settings.readiness_timeout_seconds,
        ),
        _run_check(
            lambda: _check_http(http_client, settings.minio_ready_url),
            settings.readiness_timeout_seconds,
        ),
    )
    return {
        "postgres": postgres,
        "qdrant": qdrant,
        "minio": minio,
    }
