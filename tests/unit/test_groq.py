import json

import httpx
import pytest

from app.agent.groq import GroqLlm, resolve_groq_model
from app.agent.llm import LlmMessage, LlmRequest, LlmResponseError, LlmServerError, LlmTimeoutError


def _llm(handler: object) -> GroqLlm:
    return GroqLlm(
        api_key="gsk_test",
        model="llama-3.3-70b-versatile",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_resolve_groq_model_ignores_leftover_gemini() -> None:
    assert resolve_groq_model("gemini-3.8-flash") == "openai/gpt-oss-20b"
    assert resolve_groq_model("llama-3.3-70b-versatile") == "openai/gpt-oss-20b"
    assert resolve_groq_model("qwen/qwen3.8-27b") == "qwen/qwen3.8-27b"


def test_groq_generate_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["model"] == "llama-3.3-70b-versatile"
        assert payload["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Theo dữ liệu đã duyệt. Nguồn: TL03."}}]},
        )

    response = _llm(handler).complete(
        LlmRequest(
            purpose="generate",
            messages=[
                LlmMessage(role="system", content="sys"),
                LlmMessage(role="user", content="điểm I"),
            ],
        )
    )
    assert "TL03" in response.text
    assert response.parsed is None


def test_groq_json_schema_for_gpt_oss() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["model"] == "openai/gpt-oss-20b"
        assert payload["reasoning_effort"] == "low"
        assert payload["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"scope_type":"answer_allowed"}'}}]},
        )

    llm = GroqLlm(
        api_key="gsk_test",
        model="openai/gpt-oss-20b",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )
    response = llm.complete(
        LlmRequest(
            purpose="routing",
            messages=[LlmMessage(role="system", content="schema")],
            json_schema={"type": "object", "properties": {"scope_type": {"type": "string"}}},
        )
    )
    assert response.parsed == {"scope_type": "answer_allowed"}


def test_groq_json_object_for_llama() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["response_format"] == {"type": "json_object"}
        assert "JSON object" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"scope_type":"answer_allowed"}'}}]},
        )

    response = _llm(handler).complete(
        LlmRequest(
            purpose="routing",
            messages=[LlmMessage(role="system", content="Chỉ trả JSON theo schema.")],
            json_schema={"type": "object", "properties": {"scope_type": {"type": "string"}}},
        )
    )
    assert response.parsed == {"scope_type": "answer_allowed"}


def test_groq_maps_timeout_and_rate_limit() -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, text="deadline")

    with pytest.raises(LlmTimeoutError):
        _llm(timeout).complete(LlmRequest(purpose="generate", messages=[]))

    def busy(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit reached")

    with pytest.raises(LlmServerError, match="429"):
        _llm(busy).complete(LlmRequest(purpose="generate", messages=[]))

    def bad_key(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid")

    with pytest.raises(LlmResponseError, match="API key"):
        _llm(bad_key).complete(LlmRequest(purpose="generate", messages=[]))
