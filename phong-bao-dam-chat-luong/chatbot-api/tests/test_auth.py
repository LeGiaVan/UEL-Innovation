from app.core.security import decode_session_jwt, encode_session_jwt, resolve_role

from tests.conftest import ApiClient, FakeDB, fake_google, isolated_app, logged_in_client, make_settings
from app.factory import create_app


def test_resolve_role() -> None:
    assert resolve_role("sv@gmail.com", ["a@uel.edu.vn"]) == "member"
    assert resolve_role("a@uel.edu.vn", ["a@uel.edu.vn"]) == "department_admin"
    assert resolve_role("A@UEL.EDU.VN", ["a@uel.edu.vn"]) == "department_admin"
    assert resolve_role("other@uel.edu.vn", ["a@uel.edu.vn"]) == "member"
    assert resolve_role("a@gmail.com", ["a@gmail.com"]) == "member"
    assert resolve_role("vanlg23416@st.uel.edu.vn", ["vanlg23416@st.uel.edu.vn"]) == "member"
    assert resolve_role("demo@gmail.com", ["demo@gmail.com"]) == "member"
    assert resolve_role("demo@gmail.com", ["demo@gmail.com"], allow_non_uel_admin=True) == "department_admin"


def test_jwt_roundtrip_department_from_server() -> None:
    token = encode_session_jwt(
        secret="t" * 32,
        sub="google-1",
        email="sv@gmail.com",
        role="member",
        department_id="pdt",
        sid="sid-1",
        ttl_hours=8,
    )
    payload = decode_session_jwt(token, "t" * 32)
    assert payload["department_id"] == "pdt"
    assert payload["role"] == "member"
    assert payload["email"] == "sv@gmail.com"


def test_auth_config_exposes_yaml_department() -> None:
    client = ApiClient(isolated_app())
    res = client.get("/api/auth/config")
    assert res.status_code == 200
    body = res.json()
    assert "google_client_id" in body
    dept = body["department"]
    assert dept["id"]
    assert dept["name"]
    assert dept["short"]
    assert "greeting" in body


def test_me_unauthenticated() -> None:
    client = ApiClient(isolated_app())
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["authenticated"] is False


def test_chat_requires_login() -> None:
    client = ApiClient(isolated_app())
    res = client.post("/api/chat/stream", json={"message": "xin chào"})
    assert res.status_code == 401


def test_google_without_client_id() -> None:
    client = ApiClient(isolated_app(google_client_id=""))
    res = client.post("/api/auth/google", json={"id_token": "x" * 24})
    assert res.status_code == 503
    assert "GOOGLE_CLIENT_ID" in res.json()["detail"]


def test_google_without_mongo() -> None:
    app = create_app(make_settings(google_client_id="cid.apps.googleusercontent.com"))
    assert app.state.db is None
    client = ApiClient(app)
    res = client.post("/api/auth/google", json={"id_token": "x" * 24})
    assert res.status_code == 503
    assert "MongoDB" in res.json()["detail"]


def test_google_login_sets_cookie_and_ignores_client_department_id() -> None:
    app = isolated_app(google_client_id="test-client.apps.googleusercontent.com")
    app.state.db = FakeDB()
    app.state.mongo_ok = True
    app.state.department = {"id": "starter", "admins": ["boss@uel.edu.vn"]}
    app.state.verify_google_id_token = fake_google("sv@gmail.com")
    client = ApiClient(app)

    res = client.post(
        "/api/auth/google",
        json={
            "id_token": "x" * 40,
            "department_id": "hack",
            "role": "department_admin",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is True
    assert body["email"] == "sv@gmail.com"
    assert body["role"] == "member"
    assert body["department_id"] == "starter"
    assert "uel_session" in res.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
    assert me.json()["department_id"] == "starter"
    assert me.json()["role"] == "member"

    chat = client.post("/api/chat/stream", json={"message": "xin chào"})
    assert chat.status_code == 200


def test_member_cannot_access_admin_api() -> None:
    client = logged_in_client(email="sv@gmail.com", admins=["boss@uel.edu.vn"])
    res = client.get("/api/admin/status")
    assert res.status_code == 403


def test_admin_can_access_admin_api() -> None:
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    me = client.get("/api/auth/me")
    assert me.json()["role"] == "department_admin"
    res = client.get("/api/admin/status")
    assert res.status_code == 200
    assert res.json()["ingest"] == "ready"


def test_gmail_in_admins_is_member_unless_yaml_allows() -> None:
    member = logged_in_client(email="demo@gmail.com", admins=["demo@gmail.com"])
    assert member.get("/api/auth/me").json()["role"] == "member"
    assert member.get("/api/admin/status").status_code == 403
    admin = logged_in_client(
        email="demo@gmail.com",
        admins=["demo@gmail.com"],
        allow_non_uel_admin=True,
    )
    assert admin.get("/api/auth/me").json()["role"] == "department_admin"
    assert admin.get("/api/admin/status").status_code == 200


def test_logout_revokes_session() -> None:
    client = logged_in_client(email="sv@gmail.com")
    assert client.get("/api/auth/me").json()["authenticated"] is True
    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.post("/api/chat/stream", json={"message": "hi"}).status_code == 401
