from fastapi.testclient import TestClient

from app.agent.models import ChatResult, Citation
from app.factory import create_app


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def invoke(self, message, **kwargs):
        self.calls.append((message, kwargs))
        return ChatResult(
            request_id="agent",
            status="answered",
            answer="<script>alert(1)</script>",
            citations=[Citation(kind="document_code", value="TL03")],
        )


def test_chat_auth_tenant_and_response(settings):
    app = create_app(settings)
    runtime = FakeRuntime()
    with TestClient(app) as client:
        app.state.agent_runtime = runtime
        assert client.post("/v1/chat", json={"message": "hello"}).status_code == 401
        headers = {"X-API-Key": settings.app_api_key.get_secret_value()}
        assert (
            client.post(
                "/v1/chat", headers=headers, json={"message": "hello", "department_id": "other"}
            ).status_code
            == 422
        )
        response = client.post("/v1/chat", headers=headers, json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["citations"][0]["value"] == "TL03"
        assert response.headers["X-Request-ID"] == response.json()["request_id"]
        assert runtime.calls[0][1]["department_id"] == settings.app_department_id
        assert (
            client.post(
                "/v1/chat", headers=headers, content=b"x" * (settings.request_max_bytes + 1)
            ).status_code
            == 413
        )
        page = client.get("/")
        assert page.status_code == 200
        assert "textContent" in page.text


def test_wrong_key_and_cors(settings, capsys):
    settings.cors_origins = ["https://chat.example.edu"]
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post("/v1/chat", headers={"X-API-Key": "wrong"}, json={"message": "hi"})
        assert response.status_code == 401
        assert "wrong" not in response.text
        preflight = client.options(
            "/v1/chat",
            headers={
                "Origin": "https://chat.example.edu",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-api-key,content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "https://chat.example.edu"
        denied = client.options(
            "/v1/chat",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert denied.status_code == 400
    output = capsys.readouterr()
    assert "wrong" not in output.out + output.err
    assert settings.app_api_key.get_secret_value() not in output.out + output.err


def test_service_failure_does_not_expose_details(settings):
    class BrokenRuntime:
        def invoke(self, *args, **kwargs):
            raise RuntimeError("private failure detail")

    app = create_app(settings)
    with TestClient(app) as client:
        app.state.agent_runtime = BrokenRuntime()
        response = client.post(
            "/v1/chat",
            headers={"X-API-Key": settings.app_api_key.get_secret_value()},
            json={"message": "hello"},
        )
        assert response.status_code == 503
        assert "private failure detail" not in response.text


def test_timeout(settings):
    import time

    class SlowRuntime:
        def invoke(self, *args, **kwargs):
            time.sleep(0.2)
            return ChatResult(request_id="agent", status="answered", answer="late")

    settings.chat_timeout_seconds = 0.02
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.agent_runtime = SlowRuntime()
        response = client.post(
            "/v1/chat",
            headers={"X-API-Key": settings.app_api_key.get_secret_value()},
            json={"message": "hello"},
        )
        assert response.status_code == 504
        assert response.headers.get("X-Request-ID")


def test_input_validation_and_special_characters(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        runtime = FakeRuntime()
        app.state.agent_runtime = runtime
        headers = {"X-API-Key": settings.app_api_key.get_secret_value()}
        for message in ("", "   ", "x" * 4001):
            assert (
                client.post("/v1/chat", headers=headers, json={"message": message}).status_code
                == 422
            )
        special = "<tag> & ' quote 漢字"
        response = client.post("/v1/chat", headers=headers, json={"message": special})
        assert response.status_code == 200
        assert runtime.calls[-1][0] == special


def test_provider_fallback_is_visible_without_exposing_error(settings):
    class FallbackRuntime:
        def invoke(self, *args, **kwargs):
            return ChatResult(
                request_id="agent",
                status="answered",
                answer="Source excerpt",
                error_message="secret provider error details",
            )

    app = create_app(settings)
    with TestClient(app) as client:
        app.state.agent_runtime = FallbackRuntime()
        result = client.post(
            "/v1/chat",
            headers={"X-API-Key": settings.app_api_key.get_secret_value()},
            json={"message": "hello"},
        )
        assert result.json()["provider_fallback"] is True
        assert "secret provider error details" not in result.text
