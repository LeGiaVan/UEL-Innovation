from fastapi.testclient import TestClient

from app.factory import create_app


def test_live() -> None:
    client = TestClient(create_app())
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_me_unauthenticated() -> None:
    client = TestClient(create_app())
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["authenticated"] is False
