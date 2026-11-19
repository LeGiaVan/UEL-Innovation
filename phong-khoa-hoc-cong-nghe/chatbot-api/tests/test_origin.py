from app.core.origins import allowed_origins
from tests.conftest import ApiClient, isolated_app, logged_in_client, make_settings


def test_chat_without_origin_is_forbidden() -> None:
    client = logged_in_client(email="sv@gmail.com")
    res = client.post(
        "/api/chat/stream",
        json={"message": "xin chào"},
        headers={"Origin": ""},
    )
    assert res.status_code == 403
    assert "Origin" in res.json()["detail"]


def test_chat_evil_origin_is_forbidden() -> None:
    client = logged_in_client(email="sv@gmail.com")
    res = client.post(
        "/api/chat/stream",
        json={"message": "xin chào"},
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403


def test_chat_localhost_origin_reaches_auth() -> None:
    client = ApiClient(isolated_app())
    res = client.post("/api/chat/stream", json={"message": "xin chào"})
    assert res.status_code == 401


def test_modules_requires_login() -> None:
    client = ApiClient(isolated_app())
    assert client.get("/api/modules").status_code == 401
    authed = logged_in_client(email="sv@gmail.com")
    res = authed.get("/api/modules")
    assert res.status_code == 200
    assert "modules" in res.json()


def test_docs_disabled_by_default() -> None:
    client = ApiClient(isolated_app())
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_enabled_when_flag_on() -> None:
    client = ApiClient(isolated_app(docs_enabled=True))
    assert client.get("/openapi.json").status_code == 200


def test_health_has_no_origin_requirement() -> None:
    client = ApiClient(isolated_app())
    assert client.get("/health/live").status_code == 200


def test_allowlist_uses_yaml_domain_not_hardcoded_rooms() -> None:
    origins = allowed_origins(
        make_settings(cookie_secure=True, cors_origins=""),
        {"domain": "pdt.chat.uel.edu.vn"},
    )
    assert "https://pdt.chat.uel.edu.vn" in origins
    assert "http://localhost:8000" in origins
    assert "https://dbcl.chat.uel.edu.vn" not in origins


def test_referer_same_host_counts_as_origin() -> None:
    client = logged_in_client(email="sv@gmail.com")
    res = client.post(
        "/api/chat/stream",
        json={"message": "xin chào"},
        headers={"Origin": "", "Referer": "http://localhost:8000/"},
    )
    assert res.status_code == 200
