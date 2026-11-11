import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.users import UserRepository
from app.schemas.api import Membership

PASSWORD = "Test-password-123!"
DEPARTMENTS = ["dbcl", "qtts", "pdt", "pns", "hc", "ctsv", "khcn"]


@pytest.fixture
def api(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_backend="sqlite",
        database_path=tmp_path / "test.sqlite3",
        login_limit=100,
        chat_limit=100,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        repo = UserRepository(app.state.db)
        ids = {}
        for username, departments, role, admin in [
            ("alice", DEPARTMENTS, "member", False),
            ("bob", ["hc"], "member", False),
            ("manager", ["hc"], "department_admin", False),
            ("root", DEPARTMENTS, "department_admin", True),
        ]:
            ids[username] = repo.create(
                username,
                PASSWORD,
                [Membership(department=d, role=role) for d in departments],
                admin,
            )
        yield client, app, ids


def headers(client, user="alice", department="hc"):
    response = client.post(
        "/api/auth/login", json={"username": user, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": "Bearer " + response.json()["access_token"],
        "X-Department-ID": department,
    }


def chat(client, h, **kwargs):
    return client.post(
        "/api/chat/stream",
        headers=h,
        json={"message": "Xin chào", "mode": "module_1", **kwargs},
    )


def done(response):
    assert response.status_code == 200, response.text
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["type"] == "done"
    assert (
        "".join(e["text"] for e in events if e["type"] == "token")
        == events[-1]["response"]
    )
    return events[-1]


def test_all_departments_and_fe_contract(api):
    client, _app, _ = api
    h = headers(client)
    for department in DEPARTMENTS:
        h["X-Department-ID"] = department
        modes = client.get("/api/chat/modes", headers=h)
        assert modes.status_code == 200
        assert len(modes.json()["modes"]) == 4
        q = client.get("/api/qa", headers=h).json()
        result = done(chat(client, h, message=q[0]["question"]))
        assert result["provider"] == "stub"
        assert q[0]["answer"] in result["response"]
        cid = result["conversation_id"]
        listing = client.get("/api/conversations?limit=200", headers=h).json()[
            "conversations"
        ]
        assert len(listing) == 1 and listing[0]["id"] == cid
        detail = client.get("/api/conversations/" + cid, headers=h).json()
        assert detail["messages"][0]["assistant_response"] == result["response"]
        done(chat(client, h, conversation_id=cid))
        assert (
            len(client.get("/api/conversations/" + cid, headers=h).json()["messages"])
            == 2
        )
    assert client.get("/api/departments", headers=h).status_code == 200
    assert client.get("/health/ready").json()["status"] == "ready"


def test_authentication_expiry_revocation_and_no_secrets(api):
    client, app, _ = api
    assert (
        client.get("/api/chat/modes", headers={"X-Department-ID": "hc"}).status_code
        == 401
    )
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": "Bearer forged"}
        ).status_code
        == 401
    )
    bad = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrong"}
    )
    assert bad.status_code == 401
    h = headers(client)
    token = h["Authorization"].split()[1]
    with app.state.db.connect() as conn:
        stored = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
        assert stored != token and len(stored) == 64
        password = conn.execute(
            "SELECT password_hash FROM users WHERE username='alice'"
        ).fetchone()[0]
        assert password.startswith("$argon2") and PASSWORD not in password
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
    h = headers(client)
    with app.state.db.connect() as conn:
        conn.execute("UPDATE sessions SET expires_at=?", (time.time() - 1,))
    assert client.get("/api/auth/me", headers=h).status_code == 401
    invalid = client.post(
        "/api/auth/login",
        json={"username": "x", "password": "sensitive-secret", "unexpected": True},
    )
    assert invalid.status_code == 422 and "sensitive-secret" not in invalid.text


def test_cross_user_department_and_mode_isolation(api):
    client, _app, _ = api
    alice = headers(client)
    cid = done(chat(client, alice))["conversation_id"]
    bob = headers(client, "bob")
    for h in [bob, {**alice, "X-Department-ID": "pns"}]:
        assert client.get("/api/conversations/" + cid, headers=h).status_code == 404
        assert chat(client, h, conversation_id=cid).status_code == 404
        assert client.delete("/api/conversations/" + cid, headers=h).status_code == 404
        assert client.get("/api/conversations", headers=h).json()["conversations"] == []
    assert (
        client.get(
            "/api/chat/modes", headers={**bob, "X-Department-ID": "pns"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/chat/modes", headers={"Authorization": alice["Authorization"]}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/chat/modes", headers={**alice, "X-Department-ID": "unknown"}
        ).status_code
        == 422
    )
    assert chat(client, alice, conversation_id=cid, mode="module_2").status_code == 409
    assert chat(client, alice, department="pns").status_code == 422
    assert chat(client, alice, message=" ").status_code == 422
    assert chat(client, alice, message="x" * 4001).status_code == 422
    assert client.get("/api/conversations?limit=999", headers=alice).status_code == 422
    assert client.delete("/api/conversations/" + cid, headers=alice).status_code == 204
    assert client.get("/api/conversations/" + cid, headers=alice).status_code == 404


def test_admin_roles_and_immediate_membership_revocation(api):
    client, _app, ids = api
    user = headers(client)
    manager = headers(client, "manager")
    admin = headers(client, "root")
    assert client.get("/api/departments/members", headers=user).status_code == 403
    assert client.get("/api/departments/members", headers=manager).status_code == 200
    body = {
        "username": "newuser",
        "password": PASSWORD,
        "memberships": [{"department": "ctsv", "role": "member"}],
    }
    assert (
        client.post("/api/admin/users", headers=manager, json=body).status_code == 403
    )
    response = client.post("/api/admin/users", headers=admin, json=body)
    assert response.status_code == 201 and "password" not in response.text
    assert (
        client.post(
            "/api/admin/users", headers=admin, json={**body, "system_admin": True}
        ).status_code
        == 422
    )
    path = f"/api/admin/users/{ids['alice']}/memberships/hc"
    assert client.delete(path, headers=admin).status_code == 204
    assert client.get("/api/chat/modes", headers=user).status_code == 403
    assert client.put(path, headers=admin, json={"role": "member"}).status_code == 204
    assert client.get("/api/chat/modes", headers=user).status_code == 200
    assert (
        client.delete(
            f"/api/admin/users/{ids['alice']}/sessions", headers=admin
        ).status_code
        == 204
    )
    assert client.get("/api/auth/me", headers=user).status_code == 401


def test_rate_limit_security_headers_and_cors(api):
    client, app, _ = api
    h = headers(client)
    app.state.settings.chat_limit = 1
    assert chat(client, h).status_code == 200
    limited = chat(client, h)
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    assert limited.headers["x-content-type-options"] == "nosniff"
    assert "x-request-id" in limited.headers
    assert "no-store" in limited.headers["cache-control"]
    preflight = client.options(
        "/api/chat/stream",
        headers={
            "Origin": "http://localhost:5177",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,x-department-id,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5177"
    assert (
        client.options(
            "/api/chat/stream",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        ).status_code
        == 400
    )
    assert (
        client.get("/health/live", headers={"host": "evil.example"}).status_code == 400
    )
    oversized = client.post("/api/chat/stream", headers=h, content=b"x" * 20000)
    assert oversized.status_code == 413
    app.state.settings.login_limit = 1
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": "wrong"}
        ).status_code
        == 429
    )


def test_persistence_and_concurrent_writes(api):
    client, app, _ = api
    h = headers(client)
    cid = done(chat(client, h))["conversation_id"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(
            pool.map(lambda _: chat(client, h, conversation_id=cid), range(5))
        )
    assert all(r.status_code == 200 for r in responses)
    with TestClient(create_app(app.state.settings)) as restarted:
        detail = restarted.get("/api/conversations/" + cid, headers=h)
        assert detail.status_code == 200
        assert len(detail.json()["messages"]) == 6


def test_openapi_and_production_defaults(api):
    client, app, _ = api
    schema = client.get("/openapi.json").json()
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
    assert "/api/chat/stream" in schema["paths"]
    assert schema["paths"]["/api/chat/stream"]["post"]["security"]
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")
    settings = Settings(
        _env_file=None,
        environment="production",
        database_backend="sqlite",
        database_path=app.state.settings.database_path,
        allowed_origins=["https://chat.example.com"],
    )
    with TestClient(create_app(settings)) as prod:
        assert prod.get("/docs").status_code == 404
        assert (
            prod.get("/health/live")
            .headers["strict-transport-security"]
            .startswith("max-age=")
        )


def test_access_logs_include_request_metadata_without_query_values(api, caplog):
    client, _app, _ = api
    with caplog.at_level("INFO", logger="chatbot.access"):
        response = client.get("/health/live?private=value")
    assert response.status_code == 200
    access_logs = [record.getMessage() for record in caplog.records]
    assert any("GET /health/live status=200" in entry for entry in access_logs)
    assert any(response.headers["x-request-id"] in entry for entry in access_logs)
    assert all("private=value" not in entry for entry in access_logs)


def test_temporary_guest_access(api):
    client, app, _ = api
    owner = headers(client)
    private_id = done(chat(client, owner))["conversation_id"]
    app.state.settings.auth_disabled = True
    for department in DEPARTMENTS:
        guest = {"X-Department-ID": department}
        assert client.get("/api/chat/modes", headers=guest).status_code == 200
        assert client.get("/api/qa", headers=guest).status_code == 200
        cid = done(chat(client, guest))["conversation_id"]
        assert client.get("/api/conversations/" + cid, headers=guest).status_code == 200
        assert (
            client.get("/api/conversations/" + private_id, headers=guest).status_code
            == 404
        )
        assert client.get("/api/departments/members", headers=guest).status_code == 403
    assert client.post("/api/auth/logout").status_code == 204
    app.state.settings.auth_disabled = False
    assert (
        client.get("/api/chat/modes", headers={"X-Department-ID": "hc"}).status_code
        == 401
    )
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            auth_disabled=True,
            allowed_origins=["https://example.com"],
        )


def test_dummy_hello_identifies_each_department(api):
    from app.services.catalog import CATALOG

    client, app, _ = api
    app.state.settings.auth_disabled = True
    for department in DEPARTMENTS:
        h = {"X-Department-ID": department}
        for message in ("hello", " HELLO! "):
            result = done(chat(client, h, message=message))
            assert result["response"].startswith(
                f"Xin chào, đây là chatbot {CATALOG[department]['name']}"
            )
            assert "dummy từ backend" in result["response"]
            history = client.get(
                "/api/conversations/" + result["conversation_id"], headers=h
            ).json()
            assert history["messages"][0]["assistant_response"] == result["response"]
