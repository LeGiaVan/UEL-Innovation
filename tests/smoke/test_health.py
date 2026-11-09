from collections.abc import Mapping

import httpx
import pytest

from app.api.routes import health
from app.core.config import Settings
from app.factory import create_app
from app.services.health import DependencyState


async def test_liveness_returns_request_id(settings: Settings) -> None:
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health/live",
                headers={"X-Request-ID": "smoke-test-request"},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "smoke-test-request"


@pytest.mark.parametrize(
    ("dependencies", "expected_status_code", "expected_status"),
    [
        (
            {"postgres": "ok", "qdrant": "ok", "minio": "ok"},
            200,
            "ready",
        ),
        (
            {"postgres": "ok", "qdrant": "error", "minio": "ok"},
            503,
            "not_ready",
        ),
    ],
)
async def test_readiness_reflects_dependency_health(
    dependencies: Mapping[str, DependencyState],
    expected_status_code: int,
    expected_status: str,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    async def fake_check_dependencies(
        *args: object,
        **kwargs: object,
    ) -> dict[str, DependencyState]:
        del args, kwargs
        return dict(dependencies)

    monkeypatch.setattr(health, "check_dependencies", fake_check_dependencies)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    assert response.status_code == expected_status_code
    assert response.json() == {
        "status": expected_status,
        "dependencies": dict(dependencies),
    }
